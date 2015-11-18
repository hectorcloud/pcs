#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baidu Yun utility, upload to and download from Baidu PCS
which is located at http://pan.baidu.com.

thanks to bypy and api.py(https://github.com/ly0/baidupcsapi).

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
    with open("pcstest_oauth", "w") as fd:
        _files = json.dumps(_files)
        fd.write(_files)
    return 0

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # when does this script start?
    time_started = datetime.datetime.now()

    requests.packages.urllib3.disable_warnings()

    usage = """
    {0} upload => from [local dir] to [remote dir]
    {0} download => from [remote dir] to [local dir]
    {0} list => show subdirs and files
    {0} delete => delete remote dir|file
    Note: remote dir is relative to /apps/pcstest_oauth
    """.format(os.path.basename(sys.argv[0]))

    if len(sys.argv) < 2:
        print(usage)
        exit(0)

    oauth_url = "https://openapi.baidu.com/oauth/2.0/authorize?response_type=token&client_id=L6g70tBRRIXLsY0Z3HwKqlRE&redirect_uri=oob&force_login=1&scope=basic+netdisk"
    print(oauth_url)
    access_token = input("please type above url in web browser and input access_token: ")
    clouddrive = PCSMinimal(access_token)

    operation = sys.argv[1]

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
        file2upload = []
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
                file2upload.append(file)

        def upload(file2upload, mutex):
            while True:
                file = None
                mutex.acquire()
                if file2upload:
                    file = file2upload[0]
                    file2upload[:] = file2upload[1:]
                else:
                    file = None
                mutex.release()
                if file:
                    # upload this file
                    # chunk size is 1M
                    size = os.path.getsize(file)
                    counter = (size+1*1024*1024-1)//(1*1024*1024)
                    for i in range(counter):
                        with open(file, "rb") as fdlocal:
                            fdlocal.seek(i*1*1024*1024, 0)
                            data = fdlocal.read(1*1024*1024)
                            # chunk filename, append four digits, like good.mp4.0001
                            # large as 10G
                            suffix = "." + ("0"*(4-len(str(i)))) + str(i)
                            fnchunk = file+suffix
                            # create this chunk file
                            with open(fnchunk, "wb") as fdremote:
                                fdremote.write(data)
                            # upload this chunk file
                            clouddrive.file_upload(fnchunk)
                            # delete this chunk file
                            os.remove(fnchunk)
                else:
                    # no file left to upload
                    return
        # upload by thread pool, size is 5*cpu_cores at the moment
        threadpool = []
        mutex = threading.Lock()
        cpu_cores = multiprocessing.cpu_count()
        # at least 6 workers
        for i in range(max(5*cpu_cores, 6)):
            th = threading.Thread(target=upload, args=(file2upload, mutex))
            th.start()
            threadpool.append(th)
        # wait files are uploaded
        for th in threadpool:
            th.join()

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
                    clouddrive.file_download(_abspathRemote)
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
                with open("pcstest_oauth", "r") as fd:
                    _files = fd.read()
                    files = json.loads(_files)
                os.remove("pcstest_oauth")
                break
        # download sequentially
        files.sort()
        # make a backup for later use, for example, integrity check
        #files_backup = list(files)

        # download by thread pool, size is 5*cpu_core at the moment
        threadpool = []
        mutex = threading.Lock()
        cpu_cores = multiprocessing.cpu_count()
        # at least 6 workers
        for i in range(max(5*cpu_cores, 6)):
            th = threading.Thread(target=download, args=(files, mutex))
            th.start()
            threadpool.append(th)
        # wait download completed
        for th in threadpool:
            th.join()
        print("info: download finished")

        # list all files in directory
        file2merge = []
        for root, dirs, files in os.walk(rootDirLocal):
            for file in files:
                file = os.path.join(root, file)
                file2merge.append(file)
        file2merge.sort()
        # recover file name by strip '.0001' ending
        filenames = [fn[:-5] for fn in file2merge]
        filenames = set(filenames)
        filenames = list(filenames)
        filenames.sort()

        # integrity check. Are all files downloaded? Are their size is 1M except last one?
        for fn in filenames:
            print("info: check file {}".format(fn))
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
                    suffix = "." + ("0"*(4-len(str(idx)))) + str(idx)
                    print("error: {} not exists".format(chunk[:-5] + suffix))
                    exit(1)
                if os.path.getsize(chunk) != 1*1024*1024:
                    print("error: size of {} not equal 1M".format(chunk))
                    exit(1)
            # last chunk
            idx = len(chunks) - 1
            chunk = chunks[idx]
            if int(chunk[-4:]) != idx:
                suffix = "." + ("0"*(4-len(str(idx)))) + str(idx)
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
        # special to "/apps/pcstest_oauth"
        if dirRemote == "/apps/pcstest_oauth":
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
