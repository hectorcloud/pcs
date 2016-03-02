# pcs
Personal Cloud Storage provided by Baidu

This utility is to upload|download to|from Baidu PCS.

###example:
####\#python main.py token
please copy url below to browser address to get Authorization Code
https://openapi.baidu.com/oauth/2.0/authorize?response_type=code&client_id=q8WE4EpCsau1oS0MplgMKNBn&redirect_uri=oob&force_login=1&scope=basic+netdisk
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

####version 1.0
account pcstest_oauth can be used untill this version.

####version 2.0
Another way to get access token. Save it for convenience.
Support non ascii character in file name, not directory name yet.
