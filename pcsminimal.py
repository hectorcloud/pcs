#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baidu Yun utility, upload to and download from Baidu PCS
which is located at http://pan.baidu.com.

thanks to bypy and api.py.

under python 3.4.3

Author: Hector Cloud
Date: Aug 1, 2015
"""

import os
import multiprocessing
import time
from pcs import *

class PCSMinimal(PCS):
    # actually is working directory
    # variable name 'workdir' more appropriate
    rootDirRemote = "/apps/pcstest_oauth/"
    # depends on user input
    rootDirLocal = "."

    def __init__(self, access_token):
        PCS.__init__(self, access_token)

    def directory_creation(self, dir):
        # must be absolute path
        dir = os.path.join(self.rootDirRemote, dir)
        dir = dir.replace("\\", "/")
        response = self.mkdir(dir)
        # check result
        if not response.ok:
            print("cannot create directory: {}".format(dir))

    def directory_deletion(self, dir):
        # must be absolute path
        dir = os.path.join(self.rootDirRemote, dir)
        response = self.delete(dir)
        # check result
        if not response.ok:
            print("cannot delete directory: {}".format(dir))

    def directory_existence(self, dir):
        # must be absolute path
        dir = os.path.join(self.rootDirRemote, dir)
        response = self.meta(dir)
        if not response.ok:
            return False
        content = response.json()
        if content["list"][0]["isdir"]:
            return True
        else:
            return False

    def directory_list(self, dir):
        """
        :param dir:
        :return: subdirectories and files, like['rachel', 'happy.mp3', ...]
        Note: NOT distinguish directory and file at the moment
        """
        # must be absolute path
        dir = os.path.join(self.rootDirRemote, dir)
        response = self.list_files(dir, by="name", order="asc")
        result = []
        if not response.ok:
            print("cannot list direcotry: {}".format(dir))
            return result
        content = response.json()
        for it in content["list"]:
            path = it["path"]
            result.append(path)
        result.sort()
        return result

    def directory_list2(self, dir):
        """
        :param dir:
        :return: subdirectories and files, like[(rachel, 1), '(happy.mp3, 0), ...]
        Note: NOT distinguish directory and file at the moment
        """
        # must be absolute path
        dir = os.path.join(self.rootDirRemote, dir)
        response = self.list_files(dir, by="name", order="asc")
        result = []
        if not response.ok:
            print("cannot list direcotry: {}".format(dir))
            return result
        content = response.json()
        for it in content["list"]:
            path = it["path"]
            isdir = it["isdir"]
            result.append((path, isdir))
        #result.sort()
        return result

    def file_upload(self, fn):
        # I don't know the exact reason why requests are blocked whole night.
        # the workaround is restart uploading after some TIMEOUT.
        # prefer multiprocessing to threading because there is no Thread.terminate()
        size = os.path.getsize(fn)
        # average speed is 5 kbps
        # residual 5 seconds if empty file
        timeout = size / (5*1024) + 5
        while True:
            p = multiprocessing.Process(target=helper_file_upload, args=(self, fn))
            p.start()
            p.join(timeout=timeout)
            if p.is_alive():
                # upload not finished yet
                p.terminate()
                time.sleep(2)
                print("info: next round [{}]".format(fn))
                # next run
                continue
            else:
                # upload finished, integrity check
                # must be absolute path
                _fn = os.path.relpath(fn, self.rootDirLocal)
                _fn = os.path.join(self.rootDirRemote, _fn)
                _fn = os.path.normpath(_fn)
                _fn = _fn.replace("\\", "/")
                response = self.meta(_fn)
                if response.ok:
                    # file size check
                    content = response.json()
                    if not content["list"][0]["isdir"]:
                        if content["list"][0]["size"] == size:
                            # upload success
                            break
                print("info: next round [{}]".format(fn))
                continue

    def file_download(self, fn):
        # download this file until success
        while True:
            p = multiprocessing.Process(target=helper_file_download, args=(self, fn))
            p.start()
            # restart if not finished within 5 minutes
            p.join(timeout=5*60)
            if p.is_alive():
                p.terminate()
                time.sleep(2)
                print("info: next round [{}]".format(fn))
                # next round
                continue
            else:
                break

    def file_existence(self, fn):
        # must be absolute path
        fn = os.path.join(self.rootDirRemote,fn)
        response = self.meta(fn)
        if not response.ok:
            return False
        content = response.json()
        if not content["list"][0]["isdir"]:
            return True
        else:
            return False

    def file_deletion(self, fn):
        # must be absolute path
        fn = os.path.join(self.rootDirRemote, fn)
        response = self.delete(fn)
        # check result
        if not response.ok:
            print("cannot delete directory: {}".format(dir))


def helper_file_upload(self, fn):
    """
    upload this file until success
    :param self: PCSMinimal
    :param fn:
    :return:
    """
    requests.packages.urllib3.disable_warnings()
    # relative path at local then join as remote path
    abslocal = os.path.join(self.rootDirLocal, fn)
    fn = os.path.relpath(fn, self.rootDirLocal)
    fn = os.path.join(self.rootDirRemote, fn)
    fn = fn.replace("\\", "/")

    # already uploaded?
    response = None
    try:
        response = self.meta(fn)
    except Exception as e:
        print("info: upload exception [{}]".format(str(e)))
    if hasattr(response, "ok") and response.ok:
        content = response.json()
        if content["list"][0]["size"] == os.path.getsize(abslocal):
            print("info: already uploaded, skip. [{}]".format(fn))
            return

    print("info: upload start[{}]".format(fn))
    response = None
    try:
        response = self.upload(fn, open(abslocal, "rb"), ondup="overwrite")
    except Exception as e:
        print("info: upload exception [{}]".format(str(e)))
    if (not hasattr(response, "ok")) or (not response.ok):
        print("error: upload [{}]".format(fn))
        # try again until success
        print("info: upload again [{}]".format(fn))
        helper_file_upload(self, abslocal)
    else:
        content = response.json()
        # size or md5
        size = content["size"]
        print("info: upload finish [{}]".format(fn))


def helper_file_download(self, fn):
    """
    1M at a time
    Range: bytes=0-99 <= 100 bytes
    :param self: PCSMinimal
    :param fn:
    :return:
    """
    requests.packages.urllib3.disable_warnings()
    # absolute path at remote
    fn = os.path.join(self.rootDirRemote, fn)
    fn = fn.replace("\\", "/")
    print("info: download start [{}]".format(fn))

    # file size
    response = None
    try:
        response = self.meta(fn)
    except Exception as e:
        print("info: download exception [{}]".format(str(e)))

    if (not hasattr(response, "ok")) or (not response.ok):
        helper_file_download(self, fn)
        return

    content = response.json()
    size = content["list"][0]["size"]

    relremote = os.path.relpath(fn, self.rootDirRemote)
    fnlocal = os.path.join(self.rootDirLocal, relremote)

    # already downloaded
    if os.path.exists(fnlocal):
        if size == os.path.getsize(fnlocal):
            print("info: already downloaded, skip. [{}]".format(fn))
            return

    response = None
    try:
        # Range: start-end
        start = 0
        if os.path.exists(fnlocal):
            start = os.path.getsize(fnlocal)
        else:
            start = 0
        end = size - 1
        if size - start <= 1*1024*1024:
            end = size - 1
        else:
            end = start+(1*1024*1024)-1
        headers = {'Range': 'bytes={}-{}'.format(str(start), str(end))}
        response = self.download(fn, headers=headers)
    except Exception as e:
        print("info: download exception [{}]".format(str(e)))
    if (not hasattr(response, "ok")) or (not response.ok):
        print("error: download not ok.Rang:{}-{}".format(str(start), str(end)))
        # continue downloading
        helper_file_download(self, fn)
    else:
        content = response._content
        mode = "ab" if os.path.exists(fnlocal) else "wb"
        with open(fnlocal, mode) as fd:
            fd.write(content)
        if size == os.path.getsize(fnlocal):
            print("info: download finish [{}]".format(fn))
        else:
            print("info: download more data")
            # continue downloading
            helper_file_download(self, fn)
