# pcs
Personal Cloud Storage provided by Baidu

This utility is to upload|download to|from Baidu PCS.

---

####Baidu is very evil. Do not trust any product it provides.

May 22, 2016

---

###basic thought:

upload each file chunk by chunk whose size is 1M. 

download each chunk and merge them together when all chunks are downloaded.

tar each file(Note: not tar all the files together, otherwise a very big file will be introduced) to handle non ascii characters in directory and filenames indirectly. Python can contain directory and filenames in tar file and handle non ascii characters, so we do need to take additional effort to deal with non ascii characters in directory and filenames. The name of each tarfile is its SHA1.

very simple encryption introduced. It's symmetric.

**one example**:

plan to upload directory `/home/pcs/videos` to cloud server. All files under this directory and subdirectories are as follows:

* /home/pcs/videos/alpha.mp4

* /home/pcs/videos/Oscar/a.mp4

* /home/pcs/videos/Oscar/b.mp4

* /home/pcs/videos/India/1.mp4

* /home/pcs/videos/India/2.mp4

Change working directory to `/home/pcs/videos` and tar each file, the following tarfiles are generated:

* /home/pcs/videos/`<alpha.mp4.tar>`

* /home/pcs/videos/`<a.mp4.tar>`

* /home/pcs/videos/`<b.mp4.tar>`  

* /home/pcs/videos/`<1.mp4.tar>`

* /home/pcs/videos/`<2.mp4.tar>`

_Note: `<xxx.tar>` is the SHA1 of the tarfile itself._

upload each file chunk by chunk and encrypt each chunk just before uploading.

---

###misc:

One day Baidu may not provide|support its API which is used in this project. What will we do then? One possible way is to exploit mail services provided by `mail.163.com` and others. We can upload each chunk of each file as attachment when sending email by SMTP and download each chunk of each file when receiving eamil by IMAP.

---

###usage example:
####\#python main.py token
please copy url below to browser address to get Authorization Code

<https://openapi.baidu.com/oauth/2.0/authorize?response_type=code&client_id=q8WE4EpCsau1oS0MplgMKNBn&redirect_uri=oob&force_login=1&scope=basic+netdisk>

Auth Code:75766861421e32350571f6a519dc7012

access token is below and will be expired 30 days later.

21.cd4592b8214552430de69f234af057a6.2592000.1459509390.1663979831-1572671

access token has been saved into file below.

/usr/bin/access_token.txt

####\#python main.py upload
local dir: .

remote dir: 1118pcs

####\#python main.py download
remote dir: 1118pcs

local dir: d:\1118pcs

####\#python main.py list
remote dir: .

####\#python main.py delete
remote dir: 1118pcs

---

####version 1.0
account pcstest_oauth can be used untill this version.

####version 2.0
Another way to get access token. Save it for convenience.

Support non ascii character in file name, not directory name yet.

####version 2.1
Tar each file into a standalone tarfile. Because tarfile contains directory and filename and handle non ascii characters automatically, we don't need to handle non ascii characters in directory and filename by ourselves.

Do not tar all the files into a single tarfile. Very big files(many GB) are not supported well on some operationg systems.

Integrity check is helped by SHA1. SHA1 is the filename of each tarfile when storing in cloud. In addition to SHA1, simple encryption is also introduced.

####version 2.2
Baidu do NOT support 'Range: bytes=0-99' anymore when downloading. Reducing chunksize to 240K so that it's possible to download one complete file at a time.
