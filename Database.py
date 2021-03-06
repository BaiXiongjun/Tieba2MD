import sqlite3
import json
import threading
from time import sleep
from queue import Queue
from zlib import crc32


class database():
    def __init__(self, pid: int):
        fileName = str(pid) + '.db'
        self._db = sqlite3.connect(database=fileName, check_same_thread=False)
        self._db.executescript('''
        CREATE TABLE IF NOT EXISTS POSTPAGE (
            PAGE INTEGER PRIMARY KEY NOT NULL,
            RES BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS MAINFLOOR (
            FLOOR INTEGER PRIMARY KEY NOT NULL,
            REPLYID INTEGER NOT NULL,
            REPLYNUM INTEGER NOT NULL,
            PUBTIME INTEGER NOT NULL,
            AUTHOR TEXT NOT NULL,
            CONTEXT BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS SUBPAGE (
            REPLYINFO INTEGER PRIMARY KEY NOT NULL,
            RES BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS SUBFLOOR (
            PUBTIME INTEGER PRIMARY KEY NOT NULL,
            MAINID INTEGER NOT NULL,
            AUTHOR TEXT NOT NULL,
            CONTEXT BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS USERS (
            USERID INTEGER PRIMARY KEY NOT NULL,
            USERNAME TEXT NOT NULL,
            USERDATA BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS IMAGES (
            LINK TEXT PRIMARY KEY NOT NULL,
            RES BLOB NOT NULL
        )''')

        self.autoCommitFlag = True
        self.__waitForCommit = 0

        def commitTimer():
            while True:
                if self.autoCommitFlag is True:
                    if self.__waitForCommit:
                        self._db.commit()
                        self.__waitForCommit = 0
                    else:
                        sleep(0.001)

        threading._start_new_thread(commitTimer, tuple())

        self.queue = Queue()
        self.getTotalChange = lambda: self._db.total_changes

    @staticmethod
    def __replyID2Hash(replyID: int, replyPageNumber: int):
        fullText = hex(replyID) + '-' + str(replyPageNumber)
        fullTextHash = crc32(fullText.encode('ascii'))
        return fullTextHash

    def checkExistPage(self, pageNumber: int):
        result = self._db.execute(
            'SELECT PAGE,RES FROM POSTPAGE WHERE PAGE = ?', (pageNumber, ))
        resultList = list(result)
        if not resultList:
            return False
        else:
            return resultList[0]

    def writePage(self, pageNumber: int, pageRes: str):
        if self.checkExistPage(pageNumber):
            return False
        self.queue.put(('INSERT INTO POSTPAGE (PAGE,RES) VALUES (?,?)',
                        (pageNumber, pageRes)))

    def checkExistFloor(self, floorNumber: int):
        result = self._db.execute(
            'SELECT FLOOR,REPLYID,REPLYNUM,PUBTIME,AUTHOR,CONTEXT FROM MAINFLOOR WHERE FLOOR = ?',
            (floorNumber, ))
        result = list(result)
        if not result:
            return False
        else:
            return result[0]

    def getlastFloorNum(self):
        result = self._db.execute(
            'SELECT FLOOR FROM MAINFLOOR ORDER BY FLOOR DESC LIMIT 1')
        result = list(result)
        if not result:
            return 0
        else:
            return int(result[0][0])

    def writeFloor(self, floorNumber: int, replyID: int, replyNum: int,
                   publishTime: int, author: str, context: str):
        if self.checkExistFloor(floorNumber):
            return False
        self.queue.put((
            'INSERT INTO MAINFLOOR (FLOOR,REPLYID,REPLYNUM,PUBTIME,AUTHOR,CONTEXT) VALUES (?,?,?,?,?,?)',
            (floorNumber, replyID, replyNum, publishTime, author, context)))

    def checkExistSubFloor(self, publishTime: int):
        result = self._db.execute(
            'SELECT PUBTIME,MAINID,AUTHOR,CONTEXT FROM SUBFLOOR WHERE PUBTIME = ?',
            (publishTime, ))
        result = list(result)
        if not list(result):
            return False
        else:
            return list(result)[0]

    def writeSubFloor(self, publishTime: int, mainFloorID: int, author: str,
                      context: str):
        if self.checkExistSubFloor(publishTime):
            return False
        self.queue.put((
            'INSERT INTO SUBFLOOR (PUBTIME,MAINID,AUTHOR,CONTEXT) VALUES (?,?,?,?)',
            (publishTime, mainFloorID, author, context)))

    def checkExistUsers(self, userID: int):
        result = self._db.execute(
            'SELECT USERID,USERNAME,USERDATA FROM USERS WHERE USERID = ?',
            (userID, ))
        result = list(result)
        if not result:
            return False
        else:
            return result[0]

    def writeUsers(self, userID: int, userName: str, context: str):
        if self.checkExistUsers(userID):
            return False
        self.queue.put(
            ('INSERT INTO USERS (USERID,USERNAME,USERDATA) VALUES (?,?,?)',
             (userID, userName, context)))

    def checkExistImage(self, imageLink: str):
        result = self._db.execute('SELECT LINK,RES FROM IMAGES WHERE LINK = ?',
                                  (imageLink, ))
        result = list(result)
        if not list(result):
            return False
        else:
            return list(result)[0]

    def writeImage(self, imageLink: str, imageRes: bytes):
        if self.checkExistImage(imageLink):
            return False

        self.queue.put(('INSERT INTO IMAGES (LINK,RES) VALUES (?,?)',
                        (imageLink, imageRes)))

    def checkExistSubPage(self, replyID: int, replyPageNumber: int):
        argsHash = self.__replyID2Hash(replyID, replyPageNumber)
        result = self._db.execute(
            'SELECT REPLYINFO,RES FROM SUBPAGE WHERE REPLYINFO = ?',
            (argsHash, ))
        result = list(result)
        if not result:
            return False
        else:
            return result[0]

    def writeSubPage(self, replyID: int, replyPageNumber: int, context: str):
        if self.checkExistSubPage(replyID, replyPageNumber):
            return False
        argsHash = self.__replyID2Hash(replyID, replyPageNumber)
        self.queue.put(('INSERT INTO SUBPAGE (REPLYINFO,RES) VALUES (?,?)',
                        (argsHash, context)))

    def executeCommand(self):
        while True:
            self._db.execute(*self.queue.get())
            self.__waitForCommit += 1
            yield self._db.total_changes