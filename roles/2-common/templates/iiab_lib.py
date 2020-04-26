'''
Common functions for IIAB
Admin Console functions are in adm_lib.py
'''
import os
import json
import subprocess
import shlex
import xml.etree.ElementTree as ET
import yaml
import iiab.iiab_const as CONST

lang_codes = {}
lang_iso2_codes = {}

def get_zim_list(path):
    '''
    Get a list of installed zims in the passed path

    Args:
      path (str): The path to search

    Returns:
      files_processed (dict): A dict all zims found and any index directory (now obsolete)
      zim_versions (dict): A dict that translates generic zim names to physically installed
    '''

    files_processed = {}
    zim_versions = {} # we don't need this unless adm cons is installed, but easier to compute now
    content = path + "/content/"
    index = path + "/index/"
    flist = os.listdir(content)
    flist.sort()
    for filename in flist:
        zimpos = filename.find(".zim")
        if zimpos != -1:
            zim_info = {}
            filename = filename[:zimpos]
            zimname = "content/" + filename + ".zim"
            zimidx = "index/" + filename + ".zim.idx"
            if zimname not in files_processed:
                if not os.path.isdir(path + "/" + zimidx): # only declare index if exists (could be embedded)
                    zimidx = None
                files_processed[zimname] = zimidx
                zimname = content + filename + ".zim"
                zimidx = index + filename + ".zim.idx"
                if filename in CONST.old_zim_map: # handle old names that don't parse
                    perma_ref = CONST.old_zim_map[filename]
                else:
                    ulpos = filename.rfind("_")
                    # but old gutenberg and some other names are not canonical
                    if filename.rfind("-") < 0: # non-canonical name
                        ulpos = filename[:ulpos].rfind("_")
                    perma_ref = filename[:ulpos]
                zim_info['file_name'] = filename
                zim_versions[perma_ref] = zim_info # if there are multiples, last should win
    return files_processed, zim_versions

def read_library_xml(lib_xml_file, kiwix_exclude_attr=[""]): # duplicated from iiab-cmdsrv
    '''
    Read zim properties from library.xml
    Returns dict of library.xml and map of zim id to zim file name (under <dev>/library/zims)

    Args:
      lib_xml_file (str): Path to file to read. Can be on removable device
      kiwix_exclude_attr (list): Zim properties to exclude from return

    Returns:
      zims_installed (dict): A dictionary holding all installed zims and their attributes
      path_to_id_map (dict): A dictionary that translates zim ids to physical names
    '''

    kiwix_exclude_attr.append("id") # don't include id
    kiwix_exclude_attr.append("favicon") # don't include large favicon
    zims_installed = {}
    path_to_id_map = {}
    try:
        tree = ET.parse(lib_xml_file)
        root = tree.getroot()
        for child in root:
            attributes = {}
            if 'id' not in child.attrib: # is this necessary? implies there are records with no book id which would break index for removal
                print("xml record missing Book Id")
            zim_id = child.attrib['id']
            for attr in child.attrib:
                if attr not in kiwix_exclude_attr:
                    attributes[attr] = child.attrib[attr] # copy if not id or in exclusion list
            zims_installed[zim_id] = attributes
            path_to_id_map[child.attrib['path']] = zim_id
    except IOError:
        zims_installed = {}
    return zims_installed, path_to_id_map

def rem_libr_xml(zim_id, kiwix_library_xml):
    '''
    Remove a zim from library.xml

    Args:
      zim_id (uuid): Id of the zim to remove
      lib_xml_file (str): Path to file to read. Can be on removable device
    '''

    command = CONST.kiwix_manage + " " + kiwix_library_xml + " remove " + zim_id
    #print command
    args = shlex.split(command)
    try:
        outp = subprocess.check_output(args)
    except subprocess.CalledProcessError as e:
        if e.returncode != 2: # skip bogus file open error in kiwix-manage
            print(outp)

def add_libr_xml(kiwix_library_xml, zim_path, zimname, zimidx):
    '''
    Add a zim to library.xml

    Args:
      kiwix_library_xml (str): Name (path) of library.xml file
      zim_path (str): Path to zim file to add
      zimname (str): Name of zim file to add
      zimidx (str): Path to separate idx directory (obsolete)

    '''
    command = CONST.kiwix_manage + " " + kiwix_library_xml + " add " + zim_path + "/" + zimname
    if zimidx:
        command += " -i " + zim_path + "/" + zimidx
    #print command
    args = shlex.split(command)
    try:
        outp = subprocess.check_output(args)

    except: #skip things that don't work
        #print 'skipping ' + zimname
        pass

def read_lang_codes():
    '''Populate the global lang_codes dictionary from CONST.lang_codes_path json file'''

    global lang_codes
    with open(CONST.lang_codes_path, "r") as f:
        reads = f.read()
        #print("menu.json:%s"%reads)
        lang_codes = json.loads(reads)

    # create iso2 index
    for lang in lang_codes:
        lang_iso2_codes[lang_codes[lang]['iso2']  ] = lang

# there is a different algorithm in get_zim_list above
def calc_perma_ref(uri):
    '''Given a path or url return the generic zim name'''
    url_slash = uri.split('/')
    url_end = url_slash[-1] # last element
    file_ref = url_end.split('.zim')[0] # true for both internal and external index
    perma_ref_parts = file_ref.split('_')
    perma_ref = perma_ref_parts[0]
    if len(perma_ref_parts) > 1:
        perma_ref_parts = perma_ref_parts[0:len(perma_ref_parts) - 1] # all but last, which should be date
        for part in perma_ref_parts[1:]: # start with 2nd
            if not part.isdigit():
                perma_ref += "_" + part
    return perma_ref

def kiwix_lang_to_iso2(zim_lang_code):
    '''Lookup the iso2 equivalent of a zim language code'''
    return lang_codes[zim_lang_code]['iso2']

def human_readable(num):
    '''Convert a number to a human readable string'''
    # return 3 significant digits and unit specifier
    # TFM 7/15/2019 change to factor of 1024, not 1000 to match similar calcs elsewhere
    num = float(num)
    units = ['', 'K', 'M', 'G']
    for i in range(4):
        if num < 10.0:
            return "%.2f%s"%(num, units[i])
        if num < 100.0:
            return "%.1f%s"%(num, units[i])
        if num < 1000.0:
            return "%.0f%s"%(num, units[i])
        num /= 1024.0

def read_json(file_path):
    try:
        with open(file_path, 'r') as json_file:
            readstr = json_file.read()
            json_dict = json.loads(readstr)
        return json_dict
    except OSError as e:
        raise

def write_json_file(src_dict, target_file, sort_keys=False):
    try:
        with open(target_file, 'w', encoding='utf8') as json_file:
            json.dump(src_dict, json_file, ensure_ascii=False, indent=2, sort_keys=sort_keys)
            json_file.write("\n")  # Add newline cause Py JSON does not
    except OSError as e:
        raise

def write_iiab_local_vars(delta_vars, strip_comments=False, strip_defaults=False):
    output_lines = merge_local_vars(CONST.iiab_local_vars_file, delta_vars, strip_comments=strip_comments, strip_defaults=strip_defaults)
    with open(CONST.iiab_local_vars_file, 'w') as f:
        for line in output_lines:
            f.write(line)

def merge_local_vars(target_vars_file, delta_vars, strip_comments=False, strip_defaults=False):
    default_vars_file = CONST.iiab_repo_dir + '/vars/default_vars.yml'
    local_vars_lines = []
    output_lines = []
    local_vars = {}
    default_vars = {}
    defined = {}
    undefined = {}
    remove_defaults = []
    separator_found = False

    local_vars = read_yaml(target_vars_file)
    with open(target_vars_file) as f:
        local_vars_lines = f.readlines()

    default_vars = read_yaml(default_vars_file)
    if strip_defaults:
        for key in local_vars:
            if local_vars[key] == default_vars.get(key, None):
                remove_defaults.append(key)

    for key in delta_vars:
        if strip_defaults: # remove any keys that have default value
            if delta_vars[key] == default_vars.get(key, None):
                continue
        if key in local_vars:
           defined[key] = delta_vars[key]
        else:
           undefined[key] = delta_vars[key]

    for line in local_vars_lines:
        hash_pos = line.find('#')
        if hash_pos == 0:
            if not strip_comments:
                output_lines.append(line)
            if line.startswith("# IIAB -- following variables"):
                separator_found = True
            continue

        for key in defined:
            key_pos = line.find(key)
            if key_pos < 0:
                continue
            else:
                if hash_pos != -1 and hash_pos < key_pos: # key is commented
                    continue
                else: # substitute delta value
                    line = line.replace(str(local_vars[key]), str(defined[key]))
        # at this point substitutions are done

        copy_line = True
        if strip_comments and line == '\n':
            copy_line = False
        if strip_comments and hash_pos > 0 and line[:hash_pos].isspace(): # indented comment line
            copy_line = False
        if copy_line: # still not rid of this line?
            for key in remove_defaults: # skip keys marked for removal
                key_pos = line.find(key)
                if key_pos < 0:
                    continue
                else:
                    copy_line = False
                    break

        if copy_line:
            output_lines.append(line)

    if not separator_found:
        output_lines.append("\n\n############################################################################\n")
        output_lines.append("# IIAB -- following variables are first set by browser via the Admin Console\n")
        output_lines.append("#  They may be changed via text editor, or by the Admin Console.\n\n")

    for key in undefined:
        line = str(key) + ': ' + str(undefined[key])
        line += '\n'
        output_lines.append(line)

    return output_lines

def read_yaml(file_name, loader=yaml.SafeLoader):
    try:
        with open(file_name, 'r') as f:
            y = yaml.load(f, Loader=loader)
            return y
    except:
        raise

def subproc_run(cmdstr, shell=False, check=False):
    args = shlex.split(cmdstr)
    try:
        compl_proc = subprocess.run(args, shell=shell, check=check,
                                    universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except:
        raise
    return compl_proc

def subproc_cmd(cmdstr, shell=False):
    args = shlex.split(cmdstr)
    outp = subproc_check_output(args, shell=shell)
    return (outp)

def subproc_check_output(args, shell=False):
    try:
        outp = subprocess.check_output(args, shell=shell, universal_newlines=True, encoding='utf8')
    except:
        raise
    return outp

# Environment Functions

def get_iiab_env(name):
    ''' read iiab.env file for a value, return "" if does not exist. return all value for *'''
    iiab_env = {}
    iiab_env_var = ''
    try:
        fd = open("/etc/iiab/iiab.env", "r")
        for line in fd:
            line = line.lstrip()
            line = line.rstrip('\n')
            if len(line) == 0:
                continue
            if line[0] == "#":
                continue
            if line.find("=") == -1:
                continue
            chunks = line.split('=')
            iiab_env[chunks[0]] = chunks[1]
            if chunks[0] == name:
                iiab_env_var = chunks[1]
    except:
        pass
    finally:
        fd.close()
    if name == '*':
        return iiab_env
    else:
        return iiab_env_var
