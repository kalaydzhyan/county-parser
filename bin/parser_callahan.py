#!/usr/bin/python3

import json, glob, platform, os, argparse, subprocess
import regex as re
from cad_lib import isnotebook, ROOT_DIR, EMPTY_LIMIT

CNTY_SFFX = 'callahan'

if isnotebook():
    from tqdm.notebook import tqdm, trange
else:
    from tqdm import tqdm, trange

def clean_substrings(input_array):
    bad_substrings = ['$', '&nbsp;', '<strong>', '</strong>', ' (+)', ' (-)', ' (=)', '<', '>']
    element = ' '.join([str(entry) for entry in input_array])
    for sub in bad_substrings:
        element = element.replace(sub, '')
    element = element.replace('&amp;', '&').replace('   ', ' ').replace('  ', ' ').replace(' <br/>', ',')
    return element

def get_first_match(substring, html_lines, offset=0):
    for i, line in enumerate(html_lines):
        if substring in line:
            return html_lines[i+offset]

    return ''


if __name__ == '__main__':

    data_dir   = f'{ROOT_DIR}/data/data_{CNTY_SFFX}'
    output_dir = f'{ROOT_DIR}/output/output_{CNTY_SFFX}'
    os.makedirs(output_dir, exist_ok=True)

    all_taxes = {}
    for fname in glob.glob(f'{ROOT_DIR}/data/data_{CNTY_SFFX}/*CALLAHAN*.pdf'):
        args   = ["ps2ascii", fname]
        res    = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = res.stdout.decode('utf-8')
        lines  = output.split('\n')

        # extract all properties
        lines       = [line.strip('\r') for line in lines]
        first_lines = [i for i, line in enumerate(lines) if ' ID:' in line]
        last_lines  = [i+2 for i, line in enumerate(lines) if '=====' in line]
        ids         = [lines[i].split()[0][3:] for i in first_lines]

        # dictionary of taxes, keeping only real property
        taxes = {int(idd[1:]): lines[last_lines[i]-1].strip().split() for i, idd in enumerate(ids) if 'R' in idd}
        all_taxes.update(taxes)


    total_list = []

    for fname in tqdm(sorted(glob.glob(f'{data_dir}/*.html'))):
        with open(fname, 'r') as f:
            html_text  = f.read()
            html_lines = html_text.split('\n')


        match             = get_first_match('Property ID:', html_lines)
        prop_id           = int(re.findall('\d{9}', match)[0])

        match             = get_first_match('Legal Description:', html_lines, offset=1)
        legal_description = re.findall('>.*<', match)[0][1:-1]
        legal_description = clean_substrings([legal_description])

        match             = get_first_match('Situs Address:', html_lines)
        prop_address      = re.findall('>[^>]*</td>', match)[0][1:-5]

        match             = get_first_match('Name:<', html_lines)
        owner_name        = re.findall('>[^>]+<', match)[1][1:-1].strip()

        match             = get_first_match('Mailing Address:', html_lines)
        address_array     = [address_line[1:-1].strip().replace('  ','') for address_line in re.findall('>[^>]+<', match)[1:]]
        owner_address     =', '.join([line for line in address_array if line])
        
        try:
            match            = get_first_match('Deed Date', html_lines, offset=10)
            month, day, year = re.findall('>[^>]+<', match)[0][1:-1].split('/')
            transfer_date    = f'{year}-{int(month):02d}-{int(day):02d}'
        except:
            transfer_date    = ''

        absentee          = 'General Homestead' not in html_text

        match             = get_first_match('Improvement Homesite Value:', html_lines)
        imp_hs_val        = int(clean_substrings([re.findall('>[^>]+<', match)[1]]).replace(',',''))
        match             = get_first_match('Improvement Non-Homesite Value:', html_lines)
        imp_nhs_val       = int(clean_substrings([re.findall('>[^>]+<', match)[1]]).replace(',',''))
        imp_val           = imp_hs_val + imp_nhs_val

        empty_land        = imp_val < EMPTY_LIMIT

        match             = get_first_match('Property Use:', html_lines, offset=1)
        property_use      = re.findall('>[^>]+<', match)[0][1:-1].strip()

        match             = get_first_match('Zoning:', html_lines)
        zoning            = re.findall('>[^>]+<', match)[1][1:-1].strip()

        school_candidates = re.findall('[^>]* ISD', html_text)
        school            = school_candidates[0] if school_candidates else ''

        #TODO: check if there are situations with several lots
        match             = get_first_match('Acreage', html_lines, offset=10)
        land_area         = float(re.findall('>[^>]+<', match)[0][1:-1].replace(',','')) if match else 0

        recent_penalty = 0.0
        if prop_id in all_taxes:
            total_due          = float(all_taxes[prop_id][-1].replace(',', ''))
            balance            = float(all_taxes[prop_id][2].replace(',', ''))
            recent_penalty = total_due - balance

        prop_dict          = {
                                 'prop_id'          : prop_id,
                                 'legal_description': legal_description,
                                 'prop_address'     : prop_address,
                                 'owner_name'       : owner_name,
                                 'owner_address'    : owner_address,
                                 'transfer_date'    : transfer_date,
                                 'absentee'         : absentee,
                                 'empty_land'       : empty_land,
                                 'improvement_value': imp_val,
                                 'property_use'     : property_use,
                                 'zoning'           : zoning,
                                 'land_area'        : land_area,
#                                     'land_dict'        : land_dict,
                                 'recent_penalty'   : recent_penalty,
#                                     'recent_delinq'    : recent_delinquency,
                                 'school'           : school,
#                                     'inactive'         : inactive
                             }

        total_list.append(prop_dict)

    if total_list:
        with open(f'{output_dir}/output_{CNTY_SFFX}.json', 'w') as json_f:
            json_f.write(json.dumps(total_list))

        df = pd.DataFrame(total_list)
        df.to_csv(f'{output_dir}/output_{CNTY_SFFX}.csv', index=False)

        node_name = platform.node()
        if re.match('ip\-\d+\-\d+\-\d+\-\d+\..*', node_name):
            aws_dir = '/var/www/html/output'
            os.makedirs(aws_dir, exist_ok=True)
            df.to_csv(f'{aws_dir}/output_{CNTY_SFFX}.csv', index=False)
