#!/usr/bin/python3

import os, subprocess, glob, json, platform
import regex as re
import numpy as np
import pandas as pd
from cad_lib import ROOT_DIR, EMPTY_LIMIT

CNTY_SFFX   = 'callahan'

def cell_to_line(array, rows, cols, delims=', '):
    strings         = [string[slice(*cols)].strip() for string in array[slice(*rows)]]
    cleaned_strings = [string for string in strings if string]
    return delims.join(cleaned_strings)

def fix_padding(string, move_from, move_to_tuple):
    idx           = string.find(' ', move_from)
    cell_len      = move_to_tuple[1]-move_to_tuple[0]
    buffer        = string[idx+1: idx+1+cell_len].strip()
    left_padding  = ' '*(move_to_tuple[0]-idx)
    right_padding = ' '*(cell_len-len(buffer))
    
    return string[:idx]+left_padding+buffer+right_padding+string[move_to_tuple[1]:]

def extract_name_address(string):
    bad_content   = ('AGT:', 'MTG:', 'OWNER INTEREST')
    address_start = ('PO BOX', 'P O Box', '%', 'C/O', 'P. L.') + tuple(str(int('0')+i) for i in range(10))
    owner_name    = ''
    owner_address = ''
    
    if string:
        lines        = string.split(', ')
        address_flag = False
        owner_name   = lines[0]
        for line in lines[1:]:
            if any(line.startswith(bad_content) for item in bad_content):
                break
                
            address_flag = line.startswith(address_start) or address_flag
            
            if address_flag:
                owner_address = owner_address + ', ' + line if owner_address else line
            else:
                owner_name = owner_name + ' ' + line
                
    return owner_name, owner_address

def analyze_legal_description(string):
    bad_items         = ['**', 'MAP NUM:', 'DIVIDED UNITS:', 'GEO QUAD:', 'AERIAL:'] 
    delinquent        = '**' in string
    acres             = re.search('ACRES: [\d\.]*', string)
    land_area         = float(acres[0].split()[1].replace(',','')) if acres else -1.0
    idxs              = np.array([string.find(item) for item in bad_items])
    idxs              = idxs[idxs>=0]
    legal_description = string[:np.min(idxs)] if idxs.any() else string
    
    return legal_description, land_area, delinquent


if __name__ == '__main__':

    output_dir = f'{ROOT_DIR}/output/output_{CNTY_SFFX}'
    os.makedirs(output_dir, exist_ok=True)
    
    total_list = []
    
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
        ranges      = list(zip(first_lines, last_lines))

        # dictionary of properties, keeping only real property
        properties  = {idd: lines[slice(*ranges[i])] for i, idd in enumerate(ids) if 'R' in idd}

        # find column positions 
        keys = [key.strip() for key in lines[3].split('    ') if key]
        first_positions = [lines[3].find(key) for key in keys]
        last_positions  = first_positions[1:]+[None]
        positions = dict(zip(keys, zip(first_positions, last_positions)))

        for prop_id in properties:
            prop_data = properties[prop_id]

            #fixing errors in pdf2ascii conversion. Need to know all field sizes to run in a key loop...
            if len(prop_data[0][slice(*positions['OWNERSHIP'])].strip())>=28:
                prop_data[0] = fix_padding(prop_data[0], move_from=positions['OWNERSHIP'][0]+27, move_to_tuple=positions['LEGAL DESCRIPTION'])

            if len(prop_data[0][slice(*positions['LEGAL DESCRIPTION'])].strip())>=49:
                prop_data[0] = fix_padding(prop_data[0], move_from=positions['LEGAL DESCRIPTION'][0]+48, move_to_tuple=positions['EXEMPTIONS / ADDN CODING'])

            end_of_descr = [idx for idx, s in enumerate(prop_data) if 'YEAR TAXING ENTITIES' in s][0]

            prop_description = dict()
            for key in positions:
                delims = ' ' if key in ['LEGAL DESCRIPTION'] else ', '
                prop_description[key] = cell_to_line(prop_data, (0, end_of_descr), positions[key], delims=delims)

            accnt_id                  = prop_description['ACCOUNT IDENTIFICATION']
            prop_address              = ''
            
            for inf_line in accnt_id.split(', '):
                if inf_line.startswith('SITUS:'):
                    prop_address = inf_line.split(': ')[1]
                    break
                
            owner_name, owner_address = extract_name_address(prop_description['OWNERSHIP'])
            absentee                  = 'HS' not in prop_description['EXEMPTIONS / ADDN CODING']
            legal_description, land_area, delinquent = analyze_legal_description(prop_description['LEGAL DESCRIPTION'])
            recent_delinquency        = float(prop_data[-1].split()[-1].replace(',', '')) if delinquent else 0
            property_use              = prop_description['PTD'] # TODO: find a table for these codes.
            
            # figuring out if the land is vacant or almost vacant
            val_dict = dict(zip(prop_description['TYPE'].split(', '), prop_description['VALUATION'].split(', ')))
            imp_val  = 0.0

            for prop_type in val_dict:
                if 'IMP ' in prop_type:
                    imp_val += float(val_dict[prop_type].replace(',',''))
                    
            empty_land        = imp_val < EMPTY_LIMIT
            school_candidates = re.findall('\d{4}[A-Z ]*ISD',''.join(prop_data))
            school            = school_candidates[-1][5:] if school_candidates else ''
            prop_dict         = {
                                    'prop_id'          : prop_id,
                                    'legal_description': legal_description,
                                    'prop_address'     : prop_address,
                                    'owner_name'       : owner_name,
                                    'owner_address'    : owner_address,
                                    'absentee'         : absentee,
                                    'empty_land'       : empty_land,
                                    'improvement_value': int(imp_val),
                                    'property_use'     : property_use,
                                    #'zoning'           : zoning,
                                    'land_area'        : land_area,
                                    #'land_dict'        : land_dict,
                                    #'recent_penalty'   : recent_penalty,
                                    'recent_delinq'    : recent_delinquency,
                                    'school'           : school,
                                    #'inactive'         : inactive
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
