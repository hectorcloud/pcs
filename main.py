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
        for m in result.split("  \r\n")[1:-1]:
            totalMem += int(m)

    if isLinux:
        meminfo = open('/proc/meminfo').read()
        matched = re.search(r'^MemTotal:\s+(\d+)', meminfo)
        if matched:
            totalMem_kB = int(matched.groups()[0])
            totalMem = totalMem_kB * 1024

    return totalMem

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

    if operation == "upload":
        dirLocal = input("local dir: ")
        dirRemote = input("remote dir: ")
        # reset working directory even though named as 'rootDirXxx'
        rootDirRemote = os.path.join(clouddrive.rootDirRemote, dirRemote)
        # normalize path
        rootDirRemote = os.path.normpath(rootDirRemote)
        rootDirRemote = rootDirRemote.replace("\\", "/")
        clouddrive.rootDirRemote = rootDirRemote
        if not clouddrive.directory_existence(rootDirRemote):
            clouddrive.directory_creation(rootDirRemote)
        rootDirLocal = os.path.abspath(dirLocal)
        clouddrive.rootDirLocal = rootDirLocal
        # list all files in directory and create directory in Baidu Yun
        files2upload = []
        for root, dirs, files in os.walk(rootDirLocal):
            for dir in dirs:
                # exclude hidden dirs
                fullpath = os.path.join(root, dir)
                if "/." in fullpath:
                    continue
                # if not exists in Baidu Yun, create this directory
                absdir = os.path.join(root, dir)
                reldir = os.path.relpath(absdir, rootDirLocal)
                if not clouddrive.directory_existence(reldir):
                    clouddrive.directory_creation(reldir)
            for file in files:
                # exclude hidden dirs
                if "/." in root:
                    continue
                # exclude hidden files
                if file.startswith("."):
                    continue
                # exclude undeleted chunk file last time
                if re.search(r"\.\d{4}$", file):
                    continue
                file = os.path.join(root, file)
                # add to upload list
                files2upload.append(file)

        def upload(chunks2upload, mutex):
            while True:
                chunk = None
                mutex.acquire()
                if chunks2upload:
                    chunk = chunks2upload[0]
                    chunks2upload[:] = chunks2upload[1:]
                else:
                    chunk = None
                mutex.release()
                if chunk:
                    # upload this chunk of size 1M
                    # split suffix, e.g. '.0000'
                    abspath = chunk[:-5]
                    offset = int(chunk[-4:])
                    # avoid non ascii characters
                    dirname, filename = os.path.split(abspath)
                    # on Windows 'mbcs' means 'utf-8'
                    sysencode = sys.getfilesystemencoding()
                    isWindows = sys.platform.startswith("win")
                    if isWindows and sysencode == 'mbcs':
                        sysencode = 'utf-8'
                    filename = filename.encode(sysencode, 'surrogateescape')
                    filename = base64.b64encode(filename, altchars=b"-_")
                    filename = filename.decode()
                    chunk_backup = chunk
                    chunk = os.path.join(dirname, filename+"."+str(offset).zfill(4))
                    with open(abspath, "rb") as fdlocal:
                        fdlocal.seek(offset*1*1024*1024, 0)
                        data = fdlocal.read(1*1024*1024)
                        # create this chunk file
                        with open(chunk, "wb") as fdremote:
                            fdremote.write(data)
                    # upload this chunk file
                    # process creation may fail due to not enough memory
                    try:
                        clouddrive.file_upload(chunk)
                    except Exception as e:
                        print(e)
                        os.remove(chunk)
                        # return this chunk to task queue, then exit
                        mutex.acquire()
                        chunks2upload.insert(0, chunk_backup)
                        mutex.release()
                        return
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
        for i in range(max(cpu_cores, mem_size//(16*1024**2))):
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
                    _abspathRemote = files[0]
                    files[:] = files[1:]
                else:
                    _abspathRemote = None
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
        for i in range(max(cpu_cores, mem_size//(16*1024**2))):
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
        for fn in filenames:
            print("info: merge file {}".format(fn))
            for chunk in file2merge:
                if (fn == chunk[:-5]) and re.fullmatch(r"\.\d{4}", chunk[-5:]):
                    with open(chunk, "rb") as fd:
                        data = fd.read()
                        fd.close()
                        with open(fn, "ab") as fd:
                            fd.write(data)
                            fd.close()
                    # remove chunk file due to merged
                    os.remove(chunk)
            # filename base64 decode
            dirname, filename = os.path.split(fn)
            filename = filename.encode()
            filename = base64.b64decode(filename, altchars=b"-_")
            # on Windows 'mbcs' means 'utf-8'
            sysencode = sys.getfilesystemencoding()
            isWindows = sys.platform.startswith("win")
            if isWindows and sysencode == 'mbcs':
                sysencode = 'utf-8'
            filename = filename.decode(sysencode, 'surrogateescape')
            new_fn = os.path.join(dirname, filename)
            os.rename(fn, new_fn)

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
