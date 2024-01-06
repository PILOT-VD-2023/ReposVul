import pandas as pd
import json
import random
import re
import os
import copy
import time
from itertools import groupby
from http import HTTPStatus
from tqdm import tqdm
import requests
import dashscope
from dashscope import Generation
from http import HTTPStatus
import csv
import pandas as pd
count = 0
yes = 0
uncertain = 0
no = 0

def chat_single_qwen(question_str, short = True):
    api_key = [
    ]
    global count
    dashscope.api_key=api_key[count%len(api_key)] # TOKEN HERE TODO

    if short:
        response=Generation.call(
            model=dashscope.Generation.Models.qwen_max,
            prompt=question_str,
        )
    else:
        time.sleep(6)
        response=Generation.call(
            model='qwen-max-longcontext',
            prompt=question_str,
        )

    return response

def get_answer(answer):

    if 'YES' in answer:
        return 'YES'
    elif 'NO' in answer:
        return 'NO'
    else:
        return 'UNCERTAIN'
    
def question_answer(language, file_name, write_name):
    
    Max_patch = 2000*5 

    # 读取CSV文件,pd读取格式貌似有问题
    with open(file_name, "r",encoding = "utf-8") as r:
        content = r.readlines()
        for i in range(len(content)):
            each = content[i]
            record_dict = json.loads(each)
            CWEs = record_dict['cwe_id'] # list

            CWE_info =  ''
            
            if len(CWEs) > 0:
                for i, CWE in enumerate(CWEs):
                    with open('CWE.csv', 'r', encoding='utf-8') as csvfile:
                        csv_reader = csv.reader(csvfile)
                        cnt = 0
                        desription = ''
                        mitigations = ''
                        for row in csv_reader:
                            if cnt != 0:
                                CWE_id = CWE.split('-')[1]
                                if row[0] == CWE_id:
                                    desription = row[4]
                                    mitigations = row[16]
                                    break
                            cnt += 1

                    CWE_info += f'[CWE {i+1} start]: ' + CWE + ' ' + desription + ' ' + mitigations + ' ' + f' [CWE {i+1} end]' + '\n'

                    
            ori_message = record_dict['commit_message']
            details = record_dict['details']

            # 收集完成构造prompt
            system_message = ''' You are now an expert in code vulnerability and patch fixes. \
            You will be provided with a CVE(Common Vulnerabilities and Exposures) with CWE(Common Weakness Enumeration) information, \
            method for reference of the CWE. \
            You will also be provided a patch, including the commit message of the patch, the modifications to the file invovled in the patch, the function or structure of the modifications in the file.\
            Note that each patch involves multiple files so that the specific modification to this file in the patch may or may not be related to the CVE fix. '''

            prompt_OSL = ''

            for idx, detail in enumerate(details):
                
                prompt = prompt_OSL + system_message + ' ' + '[CWE information]: ' + CWE_info +  ' ' + '[Commit Message]: ' + ori_message + ' '
                prompt_long = prompt
                prompt_short = prompt
                functions_patchs = detail['functions_patchs']
                functions_patchs_remain = detail['functions_patchs_remain']
                answer_prompt = '''\nYou should check whether modifications in the modified file is related to the CVE and just answer "YES" or "NO" or "UNCERTAIN"'''

                for idx1, function_patch in enumerate(functions_patchs):
                    patch_prompt = f'[Modification {idx1} Start]: ' + function_patch['patch'] + f'[Modification {idx1 } End]' + '\n'
                    function_prompt = f'[Function or Structure of Modification {idx1} Start]: ' + function_patch['function'] + f'[Function or Structure of Modification {idx1 } End]' + '\n'
                    
                    prompt_short += patch_prompt
                    prompt_long += patch_prompt + function_prompt

                temp = len(functions_patchs)
                for idx2, function_patch_remain in enumerate(functions_patchs_remain):
                    patch_prompt = f'[Modification {temp + idx2} Start]: ' + function_patch_remain + f'[Modification {temp + idx2} End]' + '\n'
                    prompt_short += patch_prompt
                    prompt_long += patch_prompt

                prompt_long += answer_prompt
                prompt_short += answer_prompt

                Max_try = 10
                tried = 0
                got_ans = False
                answer = ''
                global count

                try:
                    # 短文本模型
                    while tried < Max_try and not got_ans:
                        response = chat_single_qwen(prompt_long)
                        if response.status_code == HTTPStatus.OK:
                            got_ans = True
                            answer = response.output.text
                            length = response.usage.input_tokens
                        elif response.message == "Range of input length should be [1, 6000]":
                            break
                        elif response.message == "Requests rate limit exceeded, please try again later.":
                            print("Too quick")
                            count += 1
                        else:
                            tried += 1
                            with open('./log.txt', 'a', encoding='utf-8') as f:
                                f.write('error!'+ response.message + '\n')
                        count += 1
                    # 长文本模型
                    while tried < Max_try and not got_ans:
                        count += 1
                        response = chat_single_qwen(prompt_long, short=False)
                        if response.status_code == HTTPStatus.OK:
                            got_ans = True
                            answer = response.output.text
                            length = response.usage.input_tokens
                            print(length)
                        elif response.message == "Range of input length should be [1, 27952]":
                            break
                        elif response.message == "Requests rate limit exceeded, please try again later.":
                            print("Too quick")
                            count += 1
                            tried += 1
                        else:
                            tried += 1
                            with open('./log.txt', 'a', encoding='utf-8') as f:
                                f.write('error!'+ response.message + '\n')
                    # 去除文件代码的长文本模型
                    while tried < Max_try and not got_ans:
                        count += 1

                        response = chat_single_qwen(prompt_short, short=False)
                        if response.status_code == HTTPStatus.OK:
                            got_ans = True
                            answer = response.output.text
                            length = response.usage.input_tokens
                        elif response.message == "Range of input length should be [1, 27952]":
                            break
                        elif response.message == "Requests rate limit exceeded, please try again later.":
                            print("Too quick")
                            count += 1
                            tried += 1
                        else:
                            tried += 1
                            with open('./log.txt', 'a', encoding='utf-8') as f:
                                f.write('error!'+ response.message + '\n')

                except Exception as e:
                    print(e)

                record_dict_new = {}
                if answer == '':
                    answer = 'UNCERTAIN'
                if answer != '' :
                    answer = get_answer(answer)
                    # record_dict_new['answer'] = answer
                    record_dict['details'][idx]['llm_check_new1'] = answer
         
            with open(write_name, 'a', encoding='utf-8') as f2:
                # jsonobj = json.dumps(record_dict_new, ensure_ascii=False)
                jsonobj = json.dumps(record_dict, ensure_ascii=False)
                f2.write(jsonobj + '\n')

    return 1

def question_answer_last(language, file_name, write_name):
    
    Max_patch = 2000*5 

    # 读取CSV文件,pd读取格式貌似有问题
    with open(file_name, "r",encoding = "utf-8") as r:
        content = r.readlines()
        for i in range(len(content)):
            each = content[i]
            record_dict = json.loads(each)
            CWEs = record_dict['cwe_id'] # list

            CWE_info =  ''
            
            if len(CWEs) > 0:
                for i, CWE in enumerate(CWEs):
                    with open('CWE.csv', 'r', encoding='utf-8') as csvfile:
                        csv_reader = csv.reader(csvfile)
                        cnt = 0
                        desription = ''
                        mitigations = ''
                        for row in csv_reader:
                            if cnt != 0:
                                CWE_id = CWE.split('-')[1]
                                if row[0] == CWE_id:
                                    desription = row[4]
                                    mitigations = row[16]
                                    break
                            cnt += 1

                    CWE_info += f'[CWE {i+1} start]: ' + CWE + ' ' + desription + ' ' + mitigations + ' ' + f' [CWE {i+1} end]' + '\n'

                    
            ori_message = record_dict['commit_message']
            details = record_dict['details']

            # 收集完成构造prompt
            system_message = ''' You are now an expert in code vulnerability and patch fixes. \
            You will be provided with a CVE (Common Vulnerabilities and Exposures) with CWE(Common Weakness Enumeration) information, \
            method for reference of the CWE. \
            You will also be provided a file in the patch, including the commit message of the patch, the modifications to the file invovled in the patch, the function or structure of the modifications in the file.\
            Moreover, 
            Note that each patch involves multiple files so that the specific modification to this file in the patch may or may not be related to the CVE fix. '''

            prompt_OSL = ''

            for idx, detail in enumerate(details):
                
                if detail['agree_check'] = -1 and detail['file_language'] in language:

                    prompt = prompt_OSL + system_message + ' ' + '[CWE information]: ' + CWE_info +  ' ' + '[Commit Message]: ' + ori_message + ' '
                    prompt_long = prompt
                    prompt_short = prompt
                    functions_patchs = detail['functions_patchs']
                    functions_patchs_remain = detail['functions_patchs_remain']
                    answer_prompt = '''\nYou should check whether modifications in the modified file is related to the CVE and just answer "YES" or "NO"'''

                    for idx1, function_patch in enumerate(functions_patchs):
                        patch_prompt = f'[Modification {idx1} Start]: ' + function_patch['patch'] + f'[Modification {idx1 } End]' + '\n'
                        function_prompt = f'[Function or Structure of Modification {idx1} Start]: ' + function_patch['function'] + f'[Function or Structure of Modification {idx1 } End]' + '\n'
                        
                        prompt_short += patch_prompt
                        prompt_long += patch_prompt + function_prompt

                    temp = len(functions_patchs)
                    for idx2, function_patch_remain in enumerate(functions_patchs_remain):
                        patch_prompt = f'[Modification {temp + idx2} Start]: ' + function_patch_remain + f'[Modification {temp + idx2} End]' + '\n'
                        prompt_short += patch_prompt
                        prompt_long += patch_prompt

                    prompt_long += answer_prompt
                    prompt_short += answer_prompt

                    Max_try = 20
                    tried = 0
                    got_ans = False
                    answer = ''
                    global count

                    try:
                        # 短文本模型
                        while tried < Max_try and not got_ans:
                            response = chat_single_qwen(prompt_long)
                            if response.status_code == HTTPStatus.OK:
                                got_ans = True
                                answer = response.output.text
                                length = response.usage.input_tokens
                            elif response.message == "Range of input length should be [1, 6000]":
                                break
                            elif response.message == "Requests rate limit exceeded, please try again later.":
                                print("Too quick")
                                count += 1
                            else:
                                tried += 1
                                with open('./log.txt', 'a', encoding='utf-8') as f:
                                    f.write('error!'+ response.message + '\n')
                            count += 1
                        # 长文本模型
                        while tried < Max_try and not got_ans:
                            count += 1
                            response = chat_single_qwen(prompt_long, short=False)
                            if response.status_code == HTTPStatus.OK:
                                got_ans = True
                                answer = response.output.text
                                length = response.usage.input_tokens
                                print(length)
                            elif response.message == "Range of input length should be [1, 27952]":
                                break
                            elif response.message == "Requests rate limit exceeded, please try again later.":
                                print("Too quick")
                                count += 1
                                tried += 1
                            else:
                                tried += 1
                                with open('./log.txt', 'a', encoding='utf-8') as f:
                                    f.write('error!'+ response.message + '\n')
                        # 去除文件代码的长文本模型
                        while tried < Max_try and not got_ans:
                            count += 1

                            response = chat_single_qwen(prompt_short, short=False)
                            if response.status_code == HTTPStatus.OK:
                                got_ans = True
                                answer = response.output.text
                                length = response.usage.input_tokens
                            elif response.message == "Range of input length should be [1, 27952]":
                                break
                            elif response.message == "Requests rate limit exceeded, please try again later.":
                                print("Too quick")
                                count += 1
                                tried += 1
                            else:
                                tried += 1
                                with open('./log.txt', 'a', encoding='utf-8') as f:
                                    f.write('error!'+ response.message + '\n')

                    except Exception as e:
                        print(e)

                    record_dict_new = {}
                    if answer == '':
                        answer = 'UNCERTAIN'
                    if answer != '' :
                        answer = get_answer(answer)
                        record_dict['details'][idx]['agree_check'] = answer
            
                with open(write_name, 'a', encoding='utf-8') as f2:
                    jsonobj = json.dumps(record_dict, ensure_ascii=False)
                    f2.write(jsonobj + '\n')

    return 1

def main():

    language = ["c", "h"]
    file_name = '/data/xcwen/Challenge/Method/LLM/language_merge/merge_C.jsonl' 
    write_name = '/data/xcwen/Challenge/Method/LLM/language_last/merge_C.jsonl'  
    question_answer_last(language, file_name, write_name)
    
    
    language = ["cpp", "cc", "h"]
    file_name = '/data/xcwen/Challenge/Method/LLM/language_merge/merge_C++.jsonl'  
    write_name = '/data/xcwen/Challenge/Method/LLM/language_last/merge_C++.jsonl'  
    question_answer_last(language, file_name, write_name)

    language = ["java"]
    file_name = '/data/xcwen/Challenge/Method/LLM/language_merge/merge_Java.jsonl'  
    write_name = '/data/xcwen/Challenge/Method/LLM/language_last/merge_Java.jsonl'  
    question_answer_last(language, file_name, write_name)

    language = ["python"]
    file_name = '/data/xcwen/Challenge/Method/LLM/language_merge/merge_Python.jsonl' 
    write_name = '/data/xcwen/Challenge/Method/LLM/language_last/merge_Python.jsonl'  
    question_answer_last(language, file_name, write_name)

main()