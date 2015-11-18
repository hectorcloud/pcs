# pcs
Personal Cloud Storage provided by Baidu

This utility is help upload to or download from Baidu PCS.

###example:
####\#python main.py upload
https://openapi.baidu.com/oauth/2.0/authorize?response_type=token&client_id=L6g70tBRRIXLsY0Z3HwKqlRE&redirect_uri=oob&force_login=1&scope=basic+netdisk
please type above url in web browser and input access_token: 23.9d3041673d0f981ae3f3b61b606b9450.2592000.1449318585.1
663977831-23832

local dir: .

remote dir: 1118pcs

####\#python main.py download
https://openapi.baidu.com/oauth/2.0/authorize?response_type=token&client_id=L6g70tBRRIXLsY0Z3HwKqlRE&redirect_uri=oob&force_login=1&scope=basic+netdisk
please type above url in web browser and input access_token: 23.9d3041673d0f981ae3f3b61b606b9450.2592000.1449318585.1
663977831-23832

remote dir: 1118pcs

local dir: d:\1118pcs

####\#python main.py list
https://openapi.baidu.com/oauth/2.0/authorize?response_type=token&client_id=L6g70tBRRIXLsY0Z3HwKqlRE&redirect_uri=oob&force_login=1&scope=basic+netdisk
please type above url in web browser and input access_token: 23.9d3041673d0f981ae3f3b61b606b9450.2592000.1449318585.1
663977831-23832

remote dir: .

####\#python main.py delete
https://openapi.baidu.com/oauth/2.0/authorize?response_type=token&client_id=L6g70tBRRIXLsY0Z3HwKqlRE&redirect_uri=oob&force_login=1&scope=basic+netdisk
please type above url in web browser and input access_token: 23.9d3041673d0f981ae3f3b61b606b9450.2592000.1449318585.1
663977831-23832

remote dir: 1118pcs
