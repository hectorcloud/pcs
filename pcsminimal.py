#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baidu Yun utility, upload to and download from Baidu PCS
which is located at http://pan.baidu.com.

thanks to bypy and api.py.

under python 3.4.3

Author: Hector Cloud
Date: Aug 1, 2015

2015-11-18
  handle network connection exceptions or Baidu PCS server exception.
"""

import os
import multiprocessing
import time
import urllib.parse
from pcs import *


class PCSMinimal(PCS):
    # actually is working directory
    # variable name 'workdir' more appropriate
    rootDirRemote = "/apps/bypy/"
    # depends on user input
    rootDirLocal = "."

    def __init__(self, access_token):
        PCS.__init__(self, access_token)

    def directory_creation(self, _dir):
        while True:
            p = multiprocessing.Process(target=helper_directory_creation, args=(self, _dir))
            p.start()
            # estimate is 60 seconds
            p.join(timeout=60)
            if p.is_alive():
                p.terminate()
                time.sleep(2)
            else:
                break

    def directory_deletion(self, dir):
        # must be absolute path
        dir = os.path.join(self.rootDirRemote, dir)
        dir = dir.replace("\\", "/")
        try:
            response = self.delete(dir)
            # check result
            if not response.ok:
                print("cannot delete directory: {}".format(dir))
        except Exception as e:
            print(e)

    def directory_existence(self, dir):
        # must be absolute path
        dir = os.path.join(self.rootDirRemote, dir)
        dir = dir.replace("\\", "/")
        try:
            response = self.meta(dir)
            if not response.ok:
                return False
            content = response.json()
            if content["list"][0]["isdir"]:
                return True
            else:
                return False
        except Exception as e:
            print(e)

    def directory_list(self, dir):
        """
        :param dir:
        :return: subdirectories and files, like['rachel', 'happy.mp3', ...]
        Note: NOT distinguish directory and file at the moment
        """
        # must be absolute path
        dir = os.path.join(self.rootDirRemote, dir)
        dir = dir.replace("\\", "/")
        result = []
        try:
            response = self.list_files(dir, by="name", order="asc")
            if not response.ok:
                print("cannot list direcotry: {}".format(dir))
                return result
            content = response.json()
            for it in content["list"]:
                path = it["path"]
                result.append(path)
            result.sort()
        except Exception as e:
            print(e)
        return result

    def directory_list2(self, dir):
        """
        :param dir:
        :return: subdirectories and files, like[(rachel, 1), '(happy.mp3, 0), ...]
        Note: distinguish directory and file
        """
        # must be absolute path
        dir = os.path.join(self.rootDirRemote, dir)
        dir = dir.replace("\\", "/")
        result = []
        try:
            response = self.list_files(dir, by="name", order="asc")
            if not response.ok:
                print("cannot list direcotry: {}".format(dir))
                return result
            content = response.json()
            for it in content["list"]:
                path = it["path"]
                isdir = it["isdir"]
                result.append((path, isdir))
        except Exception as e:
            print(e)
        # result.sort()
        return result

    def file_upload(self, fn):
        # I don't know the exact reason why requests are stuck whole night.
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
                print("info: next round [{fn}]".format(fn=fn))
                # next run
                continue
            else:
                # upload finished
                break

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
        fn = os.path.join(self.rootDirRemote, fn)
        fn = fn.replace("\\", "/")
        try:
            response = self.meta(fn)
            if not response.ok:
                return False
            content = response.json()
            if not content["list"][0]["isdir"]:
                return True
            else:
                return False
        except Exception as e:
            print(e)

    def file_deletion(self, fn):
        # must be absolute path
        fn = os.path.join(self.rootDirRemote, fn)
        fn = fn.replace("\\", "/")
        try:
            response = self.delete(fn)
            # check result
            if not response.ok:
                print("cannot delete directory: {}".format(fn))
        except Exception as e:
            print(e)


# socket may be blocked forever if it's waiting data from peer
def helper_directory_creation(self, _dir):
    # requests.packages.urllib3.disable_warnings()
    # must be absolute path
    _dir = os.path.join(self.rootDirRemote, _dir)
    _dir = _dir.replace("\\", "/")
    try:
        response = self.mkdir(_dir)
        # check result
        if not response.ok:
            print("cannot create directory: {_dir}".format(_dir=_dir))
    except Exception as e:
        print(e)


def helper_file_upload(self, local):
    """
    upload this file until success
    :param self: PCSMinimal
    :param fn:
    :return:
    """
    requests.packages.urllib3.disable_warnings()
    # relative path at local then join as remote path
    abslocal = os.path.join(self.rootDirLocal, local)
    fn = os.path.relpath(local, self.rootDirLocal)
    fn = os.path.join(self.rootDirRemote, fn)
    fn = fn.replace("\\", "/")

    # already uploaded?
    try:
        response = self.meta(fn)
        if hasattr(response, "ok") and response.ok:
            content = response.json()
            if content["list"][0]["size"] == os.path.getsize(abslocal):
                print("info: already uploaded, skip. [{fn}]".format(fn=fn))
                return
    except Exception as e:
        print("error: upload [{fn}] exception [{e}]".format(fn=fn, e=str(e)))

    print("info: upload start[{fn}]".format(fn=fn))
    try:
        response = self.upload(fn, open(abslocal, "rb"), ondup="overwrite")
        if (not hasattr(response, "ok")) or (not response.ok):
            print("error: upload [{fn}]".format(fn=fn))
            # try again until success
            print("info: upload again [{fn}]".format(fn=fn))
            helper_file_upload(self, abslocal)
            return
        else:
            content = response.json()
            # size or md5
            # size = content["size"]
            # file existence and size checking
            size = os.path.getsize(abslocal)
            response = self.meta(fn)
            if hasattr(response, "ok") and response.ok:
                # file size check
                content = response.json()
                if not content["list"][0]["isdir"]:
                    if content["list"][0]["size"] == size:
                        # upload success
                        print("info: upload finish [{}]".format(fn))
                        return
            # next round until success
            helper_file_upload(self, abslocal)
            return
    except Exception as e:
        print("error: upload [{fn}] exception [{e}]".format(fn=fn, e=str(e)))
        # next round until success
        helper_file_upload(self, abslocal)
        return


def helper_file_download(self, fn):
    """
    one complete file at a time
    :param self: PCSMinimal
    :param fn:
    :return:
    """
    requests.packages.urllib3.disable_warnings()
    # absolute path at remote
    fn = os.path.join(self.rootDirRemote, fn)
    fn = fn.replace("\\", "/")
    print("info: download start [{fn}]".format(fn=fn))

    # file size
    size = None
    try:
        response = self.meta(fn)
        if (not hasattr(response, "ok")) or (not response.ok):
            # try again until success
            helper_file_download(self, fn)
            return
        content = response.json()
        size = content["list"][0]["size"]
    except Exception as e:
        print("info: download exception [{}]".format(str(e)))
        # try again until success
        helper_file_download(self, fn)
        return

    relremote = os.path.relpath(fn, self.rootDirRemote)
    fnlocal = os.path.join(self.rootDirLocal, relremote)
    if os.name == 'nt':
        fnlocal = fnlocal.replace("/", os.sep)
    # normalize local path
    fnlocal = os.path.normpath(fnlocal)

    # already downloaded
    if os.path.exists(fnlocal):
        if size == os.path.getsize(fnlocal):
            print("info: already downloaded, skip. [{}]".format(fn))
            return

    try:
        # Range: start-end. Do NOT use 'Range:' anymore because it's not supported well
        headers = {
            'Host': 'd.pcs.baidu.com',
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:36.0) Gecko/20100101 Firefox/36.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
        }
        response = self.download(fn, headers=headers)

        if response.status_code == 302:
            location = response.headers.get('location', None)
            o = urllib.parse.urlparse(location)
            headers['Host'] = o.hostname
            response = requests.get(location, headers=headers)

        if (not hasattr(response, "ok")) or (not response.ok):
            print("error: download not ok. [{fn}]".format(fn=fn))
            # continue downloading
            helper_file_download(self, fn)
            return
        else:
            content = response.content
            # debug of requests
            """
            response.status_code
            response.headers
            response.url
            response.history
            response.request.headers
            """
            if len(content) == size:
                with open(fnlocal, 'wb') as fd:
                    fd.write(content)
                print("info: download finish [{}]".format(fn))
                return
            else:
                print("info: download next round [{fn}]".format(fn=fn))
                # continue downloading
                helper_file_download(self, fn)
                return
    except Exception as e:
        print("error: download exception [{}]".format(str(e)))
        # try again until success
        helper_file_download(self, fn)
        return
