'''
Search using curl
'''
import sys
import re
import time
import os
from datetime import datetime
import getpass # Do not show pw input
import json


# log_path = '/var/log'
pw = ''
log_path = '/tmp'
curr_path = os.path.realpath(__file__).replace('HandsFree_search.py', '')
conf_file = curr_path + 'config.json'



def logger(contents):
    nowHourTime = datetime.today().strftime('%Y%m%d_%H')
    nowDayTime = nowHourTime[:-3]
	# 로그 경로 생성
    if not(os.path.isdir(log_path)):
        os.makedirs(os.path.join(log_path))

    with open('%s/HandsFree_search-%s.log' % (log_path, nowDayTime), 'a+') as f:
        f.write('%s %s\n' % (str(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]), contents))
    
    f.close()

def date2epoch(date):
    epoch = int(datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%s'))
    # print(type(epoch), epoch)
    return epoch

def epoch2date(epoch):
    date = datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S')
    return date

# 3s
def time2sec(time):
    sec = int(time[:-1])
    # 86400 = 60s * 60m * 24h
    if time[-1] == 'd':
        sec *= 86400
    # 3600 = 60m * 60s
    elif time[-1] == 'h':
        sec *= 3600
    # 1m = 60s
    elif time[-1] == 'm':
        sec *= 60

    # print(type(sec), sec)
    return sec

# Initial settings. Create config.json file
def setting(conf_file):
    print('Start Settings')
    config = {}
    #set config
    global log_path
    log_path = input('(1/3) Pleas enter Log Directory (ex /var/log/) \n * Do not forget "/" at last) : ')
    config['log_path'] = log_path
    config['id'] = input('(2/3) Pleas enter id address (ex admin) : ')
    config['ip'] = input('(3/3) Please enter ip : (ex 00.00.00.000) : ') #'172.20.1.91'

    with open(conf_file, 'w', newline='', encoding='utf-8') as f:
        json.dump(config, f)
        logger('DEBUG Config file created.')

    print('Config file created')


def login(id, ip):
    print('Tryig Login...')
    global pw
    res = ''
    curl = 'curl -sS -k https://%s:8089/services/auth/login --data-urlencode username=%s --data-urlencode password=%s' % (ip, id, pw)
    try:
        res = os.popen(curl).read()
    except Exception as e:
        logger('ERROR Error on line {}:'.format(sys.exc_info()[-1].tb_lineno) + str(e))
    
    #login fail
    if (res.find('msg code')) == -1 or (res.find('sessionKey')) == -1 or (res.find('msg type="WARN"')) != -1:
        logger('ERROR Login Failed')
        print('Login failed.  Please check your password')
        pw = getpass.getpass('Enter password : ')
        login(id, ip)

    return True

def inputs():
    global pw
    print('Please Enter Values')
    pw = getpass.getpass('(1/6) Please enter pw (ex pw) : ')
    first_date = input('(2/6) Please enter first date (ex 2300-01-01 22:00:00) : ')
    last_date = input('(3/6) Please enter last date (ex 2400-01-01 05:00:00) : ')
    span = input('(4/6) Please enter span (ex 3h [d, h, m, s]) : ')
    spl = input('(5/6) Please enter search query (ex index=_internal) : ') #'index=_internal'
    sleeps = input('(6/6) Plese enter search time (ex 3s [d, h, m, s]) : ')

    # log_path = '/var/log'
    # id = 'admin'
    # ip = '172.20.1.91'
    # pw = '!12cloud'
    # pw = 'adminadmin'
    # first_date = '2022-01-01 00:00:00'
    # last_date = '2022-07-01 00:01:00'
    # span = '100d'
    # spl = 'index=_internal OR index=*'
    # sleeps = '5s'


    span = time2sec(span)
    sleeps = time2sec(sleeps)

    return first_date, last_date, span, spl, sleeps

# Get sid
def get_sid(curl, data):
    ncurl = curl + ' -d search=\"%s\"' % data
    # print(curl)
    try:
        res = os.popen(ncurl)
        res = res.read()
        res.close()
    except Exception as e:
        logger('ERROR Error on line {}:'.format(sys.exc_info()[-1].tb_lineno) + str(e))

    try:
        sid = re.findall('\<sid\>(.*)\<\/sid\>', res)[0]
    except IndexError as e:
        logger('ERROR Error on line {}:'.format(sys.exc_info()[-1].tb_lineno) + str(e))
        pass
    

    return sid

# Get result 
def get_jobs(curl, sid):
    res_dict = {}
    ncurl = curl + '/' + sid

    try:
        res = os.popen(ncurl)
        res = res.read()
    except Exception as e: 
        logger('ERROR Error on line {}:'.format(sys.exc_info()[-1].tb_lineno) + str(e))

    fields = ['dispatchState', 'auto_cancel', 'auto_pause', 'isDone', 'isFailed','isFinalized', 'earlistTime', 'indexEarliestTime', 'indexLatestTime', 'eventCount', 'eventFieldCount', 'eventSearch']

    res_dict['sid'] = sid
    for field in fields:
        rex = '\n*\s*\<s\:key name\=\"' + field + '\"\>(.*)' + '\<\/s\:key\>'
        val = ''
        try:
            val = re.findall(rex, res)[0]
        except IndexError:
            val = 'null'
        except Exception as e:
            logger('ERROR Error on line {}:'.format(sys.exc_info()[-1].tb_lineno) + str(e))

        res_dict[field] = val
    #Unknown sid
    # rex = '\n*\s*\<msg type\=\"FATAL\"\>(.*)\<\\msg\>'
    # val = re.findall(rex, res)[0]

    return res_dict


def start_search(curl, first_date, last_date, span, spl, sleeps):
    res = []
    earlist = first_date
    latest = last_date
    e_cnt = 0
    s_cnt = 0
    part = 0
    while earlist < last_date:
        part += 1
        latest = earlist + span
        if latest > last_date:
            latest = last_date
        data = 'search earliest=%d latest=%d %s' % (earlist, latest, spl)
        # get sid
        try:
            sid = get_sid(curl, data)
            print('sid = ', sid)
        except Exception as e: 
            logger('ERROR Error on line {}:'.format(sys.exc_info()[-1].tb_lineno) + str(e))
        d_earlist = epoch2date(earlist)
        d_latest = epoch2date(latest)
        logger('DEBUG Search Started part %d  earliest : %s  latest : %s  sid : %s' % (part, d_earlist, d_latest, sid))

        # get job info
        try:
            res_dict = get_jobs(curl, sid)
            
        except Exception as e: 
            logger('ERROR Error on line {}:'.format(sys.exc_info()[-1].tb_lineno) + str(e))

        s_cnt += 1
        # Wait to complete
        while res_dict['isDone'] == '0':
            print('part %d running. Wait %d seconds. sid : %s' %(part, sleeps, sid))
            time.sleep(sleeps)
            res_dict = get_jobs(curl, sid)
            
        # Error output when search is not completed successfully.
        if res_dict['dispatchState'] != 'DONE':
            e_cnt += 1
            logger('ERROR Search Error. Retry search part %d' % part)
            res_dict['error'] = 'ERROR'
            print('ERROR sid : %s  earlist : %s  latest : %s  search query : %s' % (sid, d_earlist, d_latest, res_dict['eventSearch']))
        else:
            res_dict['error'] = 'none'
        res_dict['earlist'] = earlist
        res_dict['latest'] = latest
        res.append(res_dict)
        earlist += span

    return res, s_cnt, e_cnt


def main():
    # Inital settings
    if not (os.path.isfile(conf_file)):
        setting(conf_file)
    
    global pw, log_path
    config = {}
    with open(conf_file, 'r', newline='', encoding='utf-8') as f:
        config = json.load(f)
    log_path = config['log_path']
    id = config['id']
    ip = config['ip']
    
    first_date, last_date, span, spl, sleeps = inputs()

    # Try login
    login(id, ip)

    # search
    print('Start Search')
    curl = 'curl -sS -u %s:%s -k https://%s:8089/services/search/jobs' %(id, pw, ip)
    logger('INFO Start Search / ' + first_date + ' to ' + last_date + ' / ' + spl)
    first_date = date2epoch(first_date)
    last_date = date2epoch(last_date)
    res, s_cnt, e_cnt = start_search(curl, first_date, last_date, span, spl, sleeps)

    print('End')
    # Log results
    if e_cnt == 0:
        logger('INFO Search Completed Successfully! Total Search : %d' % s_cnt)
    else :
        logger('DEBUG Total Search %d' % s_cnt)
        logger('ERROR Error count : %d' % e_cnt)
        str_res = ''
        for r in res:
            str_res += '    '
            str_res += str(r)
            str_res += '\n'
        logger('INFO Result :\n%s' % str_res)

def init():
    print('\n\n\n')
    name = """
    __    __                            __                   ________                          
    /  |  /  |                          /  |                 /        |                         
    $$ |  $$ |  ______   _______    ____$$ |  _______        $$$$$$$$/_____   ______    ______  
    $$ |__$$ | /      \ /       \  /    $$ | /       |______ $$ |__ /      \ /      \  /      \ 
    $$    $$ | $$$$$$  |$$$$$$$  |/$$$$$$$ |/$$$$$$$//      |$$    /$$$$$$  /$$$$$$  |/$$$$$$  |
    $$$$$$$$ | /    $$ |$$ |  $$ |$$ |  $$ |$$      \$$$$$$/ $$$$$/$$ |  $$/$$    $$ |$$    $$ |
    $$ |  $$ |/$$$$$$$ |$$ |  $$ |$$ \__$$ | $$$$$$  |       $$ |  $$ |     $$$$$$$$/ $$$$$$$$/ 
    $$ |  $$ |$$    $$ |$$ |  $$ |$$    $$ |/     $$/        $$ |  $$ |     $$       |$$       |
    $$/   $$/  $$$$$$$/ $$/   $$/  $$$$$$$/ $$$$$$$/         $$/   $$/       $$$$$$$/  $$$$$$$/ 
    """


    info = """
    * File:    HandsFree_search.py
    * Author1 :   DenverAlmighty
    * Date    :   2022-07-14
    * Version :   0.3.1
    * Git address : https://github.com/AlmightyDenver
    * Description: 
        This file contains code which makes you free from simple repeat search.
        
    """

    print(name)
    print(info)


if __name__ == '__main__':
    init()
    main()