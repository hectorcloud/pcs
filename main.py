#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baidu Yun utility, upload to and download from Baidu PCS
which is located at http://pan.baidu.com.

thanks to bypy(https://github.com/houtianze/bypy) and api.py(https://github.com/ly0/baidupcsapi).

under python 3.4.3

references:
  http://developer.baidu.com/wiki/index.php?title=docs/pcs/guide/usage_example
  http://developer.baidu.com/wiki/index.php?title=docs/pcs/rest/file_data_apis_list
Author: Hector Cloud
Date: Aug 1, 2015
"""

import sys
import os
import re
import threading
import json
import multiprocessing
import time
import datetime
import base64
import tarfile
import hashlib
import inspect
from pcsminimal import *
import requests.packages.urllib3


def file2download(clouddrive, abspathRemote):
    """
    :param clouddrive: PCSMinimal
    :param path: remote path, already absolute path
    :return:
    """
    requests.packages.urllib3.disable_warnings()

    def helper_file2download(abspathRemote):
        _files = []
        if clouddrive.directory_existence(abspathRemote):
            # create local dir
            relpath = os.path.relpath(abspathRemote, clouddrive.rootDirRemote)
            abspath = os.path.join(clouddrive.rootDirLocal, relpath)
            if not os.path.exists(abspath):
                os.mkdir(abspath)
            paths = clouddrive.directory_list2(abspathRemote)
            for (path, isdir) in paths:
                if isdir:
                    filesinsubdir = helper_file2download(path)
                    _files += filesinsubdir
                else:
                    print("info: collect file [{}]".format(path))
                    _files.append(path)

        if clouddrive.file_existence(abspathRemote):
            print("info: collect file [{}]".format(abspathRemote))
            _files.append(abspathRemote)

        return _files

    _files = helper_file2download(abspathRemote)
    with open("bypy", "w") as fd:
        _files = json.dumps(_files)
        fd.write(_files)
    return 0


# get physical memory size in bytes
def memory_size():
    totalMem = 0
    isWindows = sys.platform.startswith("win")
    isLinux = sys.platform.startswith("linux")

    if isWindows:
        process = os.popen('wmic memorychip get capacity')
        result = process.read()
        process.close()
        totalMem = 0
        result = re.sub(r"[\r\n]", r" ", result)
        for m in result.split()[1:]:
            totalMem += int(m)

    if isLinux:
        meminfo = open('/proc/meminfo').read()
        matched = re.search(r'^MemTotal:\s+(\d+)', meminfo)
        if matched:
            totalMem_kB = int(matched.groups()[0])
            totalMem = totalMem_kB * 1024

    return totalMem


# obfuscate bytes data stream
def obfuscatebytes(data):
    data = list(data)
    # XOR with 1010-0101
    obdata = [byte ^ 0xA5 for byte in data]
    obdata = bytes(obdata)
    return obdata

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # when does this script start?
    time_started = datetime.datetime.now()

    requests.packages.urllib3.disable_warnings()

    usage = """
    {0} token => get access token
    {0} upload => from [local dir] to [remote dir]
    {0} download => from [remote dir] to [local dir]
    {0} list => show subdirs and files
    {0} delete => delete remote dir|file
    Note: remote dir is relative to /apps/byby
    """.format(os.path.basename(sys.argv[0]))

    if len(sys.argv) < 2:
        print(usage)
        exit(0)

    operation = sys.argv[1]

    # on Windows 'mbcs' means 'utf-8'
    sysencode = sys.getfilesystemencoding()
    isWindows = sys.platform.startswith("win")
    if isWindows and sysencode == 'mbcs':
        sysencode = 'utf-8'
    # http://developer.baidu.com/wiki/index.php?title=docs/pcs/guide/token_authorize
    # https://github.com/houtianze/bypy
    if operation == "token":
        print("please copy url below to browser address to get Authorization Code")
        print("https://openapi.baidu.com/oauth/2.0/authorize?response_type=code&client_id=q8WE4EpCsau1oS0MplgMKNBn&redirect_uri=oob&force_login=1&scope=basic+netdisk")
        auth_code = input("Auth Code: ")
        GaeUrl = 'https://bypyoauth.appspot.com'
        OpenShiftUrl = 'https://bypy-tianze.rhcloud.com'
        HerokuUrl = 'https://bypyoauth.herokuapp.com'
        GaeRedirectUrl = GaeUrl + '/auth'
        OpenShiftRedirectUrl = OpenShiftUrl + '/auth'
        HerokuRedirectUrl = HerokuUrl + '/auth'
        kwargs = {'timeout': 60.0, 'verify': False, 'headers': {'User-Agent': 'netdisk;5.2.7.2;PC;PC-Windows;6.2.9200;WindowsBaiduYunGuanJia'}, 'params': {'code': '', 'redirect_uri': 'oob'}}
        kwargs['params']['code'] = auth_code
        for url in [HerokuRedirectUrl, OpenShiftRedirectUrl, GaeRedirectUrl]:
            r = requests.request('GET', url, **kwargs)
            if r.status_code == 200:
                access_token = r.json()['access_token']
                print('access token is below and will be expired 30 days later.')
                print(access_token)
                # save it
                script_path = os.path.abspath(inspect.stack()[0][1])
                script_dir = os.path.dirname(script_path)
                token_file = os.path.join(script_dir, "access_token.txt")
                with open(token_file, "w") as fd:
                    fd.write(access_token)
                print("access token has been saved into file below.")
                print(token_file)
                exit(0)
        else:
            print("cannot get access token, please try later.")
            exit(1)

    # access_token = input("please input access_token: ")
    # read access token from file
    access_token = None
    script_path = os.path.abspath(inspect.stack()[0][1])
    script_dir = os.path.dirname(script_path)
    token_file = os.path.join(script_dir, "access_token.txt")
    if not os.path.exists(token_file):
        print("please get token fist")
        exit(1)
    with open(token_file, "r") as fd:
        access_token = fd.read()
    clouddrive = PCSMinimal(access_token)

    # archive all the files|directories so that they're all in single file
    # another benefit is let Python handle non-ascii character if file|directory name
    # archived file is named as <sha1>.tar for integrity after downloading
    #
    # but limited by file size in OS
    if operation == "upload":
        dirLocal = input("local dir|file: ")
        dirRemote = input("remote dir: ")
        # check non-ascii character existence of remote directory
        if re.search(r"[^0-9a-zA-Z-_/=.]", dirRemote):
            print("please use usual ascii character when specifying remote directory")
            exit(0)
        # reset working directory even though named as 'rootDirXxx'
        rootDirRemote = os.path.join(clouddrive.rootDirRemote, dirRemote)
        # normalize path
        rootDirRemote = os.path.normpath(rootDirRemote)
        rootDirRemote = rootDirRemote.replace("\\", "/")
        clouddrive.rootDirRemote = rootDirRemote
        if not clouddrive.directory_existence(rootDirRemote):
            clouddrive.directory_creation(rootDirRemote)
        rootDirLocal = os.path.abspath(dirLocal)
        # if os.path.isfile(rootDirLocal):
        #    rootDirLocal,
        clouddrive.rootDirLocal = rootDirLocal
        # list all files in directory
        files2upload = []
        # unfinished of last round
        files2delete = []
        for root, dirs, files in os.walk(rootDirLocal):
            for file in files:
                file = os.path.join(root, file)
                # exclude unfinished chunk file last time
                if re.search(r"\.\d{4}$", file):
                    files2delete.append(file)
                    continue
                # exclude hidden dirs and files
                if r"/." in file or r"\." in file:
                    continue
                # add to upload list
                files2upload.append(file)
        # delete unwanted files
        for file in files2delete:
            os.remove(file)
        # relative path for archiving operation
        if os.path.isfile(rootDirLocal):
            rootDirLocal, x = os.path.split(rootDirLocal)
        os.chdir(rootDirLocal)
        files2upload = [os.path.relpath(file, rootDirLocal) for file in files2upload]
        # archive each file then delete it
        # each file will be archived separately.
        # Benefit is to preserve non-ascii file|dir name in archive.
        # archive itself is named by its SHA1 whose characters are ascii.
        # not all into a single file due to file size limit in OS
        for idx, file in enumerate(files2upload, start=0):
            _base = os.path.basename(file)
            # already archived such as last round upload
            if not re.search(r"[^0-9a-fA-F]", _base):
                # SHA1 of this file
                sha1 = hashlib.sha1()
                with open(file, "rb") as fd:
                    for chunk in iter(lambda: fd.read(1*1024*1024), b''):
                        sha1.update(chunk)
                tarname = sha1.hexdigest()
                # confirm
                if tarname == _base:
                    # move to top level in order to handle non-ascii character in file|dir name
                    os.rename(file, tarname)
                    files2upload[idx] = tarname
                    continue

            sha1 = hashlib.sha1()
            # sha1 of original file name as temporary name
            sha1.update(file.encode(sysencode, 'surrogateescape'))
            tmpname = sha1.hexdigest()
            tar = tarfile.open(tmpname, "w")
            tar.add(file)
            tar.close()
            os.remove(file)
            # sha1 of file content as file name
            sha1 = hashlib.sha1()
            with open(tmpname, "rb") as fd:
                for chunk in iter(lambda: fd.read(1*1024*1024), b''):
                    sha1.update(chunk)
            tarname = sha1.hexdigest()
            # at top level
            os.rename(tmpname, tarname)
            files2upload[idx] = tarname
        # absolute path
        files2upload = [os.path.join(rootDirLocal, file) for file in files2upload]
        files2upload.sort()
        files2upload_backup = list(files2upload)

        def upload(chunks2upload, mutex):
            while True:
                chunk = None
                mutex.acquire()
                if chunks2upload:
                    chunk = chunks2upload.pop(0)
                mutex.release()
                if chunk:
                    # upload this chunk of size 1M
                    # split suffix, e.g. '.0000'
                    abspath = chunk[:-5]
                    offset = int(chunk[-4:])
                    fdlocal = open(abspath, "rb")
                    fdlocal.seek(offset*1*1024*1024, 0)
                    _data = fdlocal.read(1*1024*1024)
                    fdlocal.close()
                    _data = obfuscatebytes(_data)
                    fdremote = open(chunk, "wb")
                    fdremote.write(_data)
                    fdremote.close()
                    # upload this chunk of file
                    # process creation may fail due to not enough memory
                    try:
                        clouddrive.file_upload(chunk)
                    except Exception as e:
                        print(e)
                        # return this chunk to task queue, then exit
                        mutex.acquire()
                        chunks2upload.insert(0, chunk)
                        mutex.release()
                    finally:
                        # delete this chunk file
                        os.remove(chunk)
                else:
                    # no chunk left to upload
                    return

        # split into chunks of size 1M
        chunks2upload = []
        for file in files2upload:
            size = os.path.getsize(file)
            for chunk in range((size+1*1024*1024-1) // (1*1024*1024)):
                chunk = file + "." + str(chunk).zfill(4)
                chunks2upload.append(chunk)

        # upload by thread pool, size can up to memory_size/16MB at the moment
        threadpool = []
        mutex = threading.Lock()
        cpu_cores = multiprocessing.cpu_count()
        mem_size = memory_size()
        # at least ? workers
        worker_no = min(max(cpu_cores, mem_size//(40*1024**2)), 64)
        for i in range(worker_no):
            th = threading.Thread(target=upload, args=(chunks2upload, mutex))
            th.start()
            threadpool.append(th)
        # wait until chunks are uploaded
        for th in threadpool:
            th.join()
        # some worker thread failed when all others finished
        if len(chunks2upload):
            upload(chunks2upload, mutex)
        # check again
        if len(chunks2upload):
            print("upload failed.")
            exit(1)
        # untar each file
        for file in files2upload_backup:
            tar = tarfile.open(file, "r")
            tar.extractall()
            tar.close()
            os.remove(file)

    if operation == "download":
        dirRemote = input("remote dir: ")
        dirLocal = input("local dir: ")

        abspathRemote = os.path.join(clouddrive.rootDirRemote, dirRemote)
        # normalize remote path
        abspathRemote = os.path.normpath(abspathRemote)
        abspathRemote = abspathRemote.replace("\\", "/")
        dirRemote = abspathRemote
        clouddrive.rootDirRemote = abspathRemote

        rootDirLocal = os.path.abspath(dirLocal)
        clouddrive.rootDirLocal = rootDirLocal

        # mkdir if not exists
        if not os.path.exists(rootDirLocal):
            os.mkdir(rootDirLocal)

        # thread to download
        def download(files, mutex):
            """
            :param path: remote file path, already absolute path
            :return:
            """
            while True:
                _abspathRemote = None
                mutex.acquire()
                if files:
                    _abspathRemote = files.pop(0)
                mutex.release()
                if _abspathRemote:
                    try:
                        clouddrive.file_download(_abspathRemote)
                    except Exception as e:
                        # return to chunk queue then exit
                        print(e)
                        mutex.acquire()
                        files.insert(0, _abspathRemote)
                        mutex.release()
                        return
                else:
                    return

        print("info: collecting files to download")
        # sockets may be blocked infinitely.
        # workaround is TIMEOUT
        files = []
        while True:
            p = multiprocessing.Process(target=file2download, args=(clouddrive, abspathRemote))
            p.start()
            # estimate is 3 minutes
            p.join(timeout=3*60)
            if p.is_alive():
                p.terminate()
                time.sleep(2)
                continue
            else:
                # IPC by file
                with open("bypy", "r") as fd:
                    _files = fd.read()
                    files = json.loads(_files)
                os.remove("bypy")
                break
        # download sequentially
        files.sort()

        # download by thread pool, size can up to memory_size/16MB at the moment
        threadpool = []
        mutex = threading.Lock()
        cpu_cores = multiprocessing.cpu_count()
        mem_size = memory_size()
        # at least ? workers
        worker_no = min(max(cpu_cores, mem_size//(40*1024**2)), 64)
        for i in range(worker_no):
            th = threading.Thread(target=download, args=(files, mutex))
            th.start()
            threadpool.append(th)
        # wait download completed
        for th in threadpool:
            th.join()
        # some worker thread failed when all others finished
        if len(files):
            download(files, mutex)
        # check again
        if len(files):
            print("download failed.")
            exit(1)
        print("info: download finished")

        # list all files in directory
        file2merge = []
        for root, dirs, files in os.walk(rootDirLocal):
            for file in files:
                file = os.path.join(root, file)
                file2merge.append(file)
        file2merge.sort()
        # recover file name by strip '.0001' ending
        filenames = [fn[:-5] for fn in file2merge if re.fullmatch(r"\.\d{4}", fn[-5:])]
        filenames = set(filenames)
        filenames = list(filenames)
        filenames.sort()

        # integrity check. Are all files downloaded? Are their size is 1M except last one?
        for fn in filenames:
            chunks = []
            for chunk in file2merge:
                if (fn == chunk[:-5]) and re.fullmatch(r"\.\d{4}", chunk[-5:]):
                    chunks.append(chunk)
            # each chunk is 1M except last one for each file
            # cardinality is continuous
            chunks.sort()
            for idx in range(len(chunks)-1):
                chunk = chunks[idx]
                if int(chunk[-4:]) != idx:
                    suffix = "." + str(idx).zfill(4)
                    print("error: {} not exists".format(chunk[:-5] + suffix))
                    exit(1)
                if os.path.getsize(chunk) != 1*1024*1024:
                    print("error: size of {} not equal 1M".format(chunk))
                    exit(1)
            # last chunk
            idx = len(chunks) - 1
            chunk = chunks[idx]
            if int(chunk[-4:]) != idx:
                suffix = "." + str(idx).zfill(4)
                print("error: {} not exists".format(chunk[:-5] + suffix))
                exit(1)

        # merge chunk files
        os.chdir(clouddrive.rootDirLocal)
        for fn in filenames:
            print("info: merge file {}".format(fn))
            for chunk in file2merge:
                if (fn == chunk[:-5]) and re.fullmatch(r"\.\d{4}", chunk[-5:]):
                    with open(chunk, "rb") as fd:
                        data = fd.read()
                        fd.close()
                        # reverse encryption
                        data = obfuscatebytes(data)
                        with open(fn, "ab") as _fd:
                            _fd.write(data)
                    # remove chunk file due to merged
                    os.remove(chunk)
            # integrity check by SHA1
            # file name is SHA1
            dirname, filename = os.path.split(fn)
            sha1 = hashlib.sha1()
            with open(fn, 'rb') as fd:
                for chunk in iter(lambda: fd.read(1*1024*1024), b''):
                    sha1.update(chunk)
            sha1 = sha1.hexdigest()
            if filename != sha1:
                print("{fn} fails SHA1 integrity check".format(fn=fn))
            # extract tar
            tar = tarfile.open(fn, "r")
            tar.extractall()
            tar.close()
            os.remove(fn)

    if operation == "list":
        dirRemote = input("remote dir: ")
        # absolute path
        dirRemote = os.path.join(clouddrive.rootDirRemote, dirRemote)
        dirRemote = os.path.normpath(dirRemote)
        dirRemote = dirRemote.replace("\\", "/")
        paths = clouddrive.directory_list(dirRemote)
        for path in paths:
            print(path)

    if operation == "delete":
        dirRemote = input("remote dir: ")
        # absolute path
        dirRemote = os.path.join(clouddrive.rootDirRemote, dirRemote)
        dirRemote = os.path.normpath(dirRemote)
        dirRemote = dirRemote.replace("\\", "/")
        # special to root directory at cloud side. e.g. "/apps/bypy"
        rootDirRemote = PCSMinimal.rootDirRemote
        rootDirRemote = os.path.normpath(rootDirRemote)
        rootDirRemote = rootDirRemote.replace("\\", "/")
        if dirRemote == rootDirRemote:
            paths = clouddrive.directory_list(dirRemote)
            for path in paths:
                clouddrive.directory_deletion(path)
        else:
            clouddrive.directory_deletion(dirRemote)

    # when does this script end?
    time_finished = datetime.datetime.now()

    # running statistics
    print("\n")
    print("time  started: {}".format(time_started))
    print("time finished: {}".format(time_finished))
    # file size transferred
    transferred = 0
    if operation in ["upload", "download"]:
        for root, dirs, files in os.walk(clouddrive.rootDirLocal):
            for file in files:
                file = os.path.join(root, file)
                transferred += os.path.getsize(file)
    # transfer speed
    time_spend = time_finished - time_started
    speed = (transferred/1024)/time_spend.total_seconds()
    if operation in ["upload"]:
        print("upload size: {} Mb".format(str(round(transferred/1024/1024))))
        print("time spent: {}".format(time_spend))
        print("upload speed: {} kbps".format(str(speed)))
    if operation in ["download"]:
        print("download size: {} Mb".format(str(round(transferred/1024/1024))))
        print("time spent: {}".format(time_spend))
        print("download speed: {} kbps".format(str(speed)))
