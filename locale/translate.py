# ---- Run with System Interpreter ----
import os
import sys
import shutil
from subprocess import call

from modules.utils.globals import APP_NAME

# App name for file name to create
# APP_NAME = 'knecht_viewer'
# modules to translate
MODULES = 'knechtapp.py modules/*.py modules/gui/*.py modules/gui/widgets/*.py ' \
          'modules/gui/wizard/*.py modules/itemview/*.py'

ENCODING_VAL = 'cp1252'

print('-------------------------')
print('Running translation tools')
print('-------------------------')
py_path = os.path.dirname(sys.executable)
print('Python executable: ' + py_path)

tool_dir = os.path.abspath(os.path.join(py_path, '..\\Tools\\i18n\\'))
if not os.path.exists(tool_dir):
    tool_dir = os.path.abspath(os.path.join(py_path, 'Tools\\i18n\\'))
print('Tools dir: ' + tool_dir)
pygettext = os.path.abspath(os.path.join(tool_dir, 'pygettext.py'))
print(pygettext)
msgfmt = os.path.abspath(os.path.join(tool_dir, 'msgfmt.py'))
print(msgfmt)
current_modules_dir = os.path.dirname(__file__)
current_modules_dir = os.path.abspath(os.path.join(current_modules_dir, '../'))
print(current_modules_dir)


class CreatePo:
    def __init__(self):
        self.pot_file = f'{APP_NAME}.pot'
        self.en_file = f'en/LC_MESSAGES/{APP_NAME}.po'
        self.out_file = f'en/LC_MESSAGES/{APP_NAME}_auto.po'

        if not os.path.exists(self.pot_file):
            print('Pot template file not found.')

        if not os.path.exists(self.en_file):
            print(self.en_file, ' not found.')

    def create_updated_en_po(self):
        msg_dict = self.read_current_po(self.en_file, self.pot_file)

        if not len(msg_dict):
            print('No data could be read from files.')
            return

        self.create_po_file(msg_dict, self.out_file)
        print(f'Created {APP_NAME}_auto.po file!')

    def update_po_de(self):
        de_file = f'de/LC_MESSAGES/{APP_NAME}.po'
        try:
            shutil.copyfile(self.pot_file, de_file)
        except Exception as e:
            print(e)

        print(f'Updated from pot: {de_file}')

    @classmethod
    def create_po_file(cls, msg_dict, file):
        if 'pot_data' not in msg_dict.keys():
            return

        current_msgid = None
        for idx, line in enumerate(msg_dict['pot_data']):
            if line.startswith('msgid'):
                current_msgid = cls.prepare_msg_line(line)
                continue

            # Fix pot file created with msgid separated by a line
            if line.startswith('"') and current_msgid == '':
                current_msgid = cls.prepare_msg_line(line)

            if line.startswith('msgstr'):
                if current_msgid in msg_dict.keys():
                    msg = msg_dict[current_msgid]
                    if msg:
                        msg_dict['pot_data'][idx] = f'msgstr "{msg}"\n'
                        current_msgid = ''

        with open(file, 'w', encoding=ENCODING_VAL) as f:
            f.writelines(msg_dict['pot_data'])

    @classmethod
    def read_current_po(cls, po_file, pot_file):
        msg_dict = dict()
        current_msgid = None

        with open(po_file, 'r', encoding=ENCODING_VAL) as f:
            msg_dict['file_data'] = f.readlines()

        with open(pot_file, 'r', encoding=ENCODING_VAL) as f:
            msg_dict['pot_data'] = f.readlines()

        for line in msg_dict['file_data']:
            if line.startswith('msgid'):
                current_msgid = cls.prepare_msg_line(line)
                continue

            # Fix pot file created with msgid separated by a line
            # msgid ""
            # "Actual msgid"
            if line.startswith('"') and current_msgid == '':
                current_msgid = cls.prepare_msg_line(line)

            if line.startswith('msgstr') and current_msgid:
                msg_dict[current_msgid] = cls.prepare_msg_line(line)

        msg_dict['file_data'] = None
        # os.rename(po_file, os.path.join(po_file, '.old'))
        return msg_dict

    @staticmethod
    def prepare_msg_line(line: str, remove_new_line=True) -> str:
        # Remove prefix
        for prefix in ('msgstr ', 'msgid '):
            if line.startswith(prefix):
                line = line[len(prefix):]
        # Remove new line
        if line.endswith('\n') and remove_new_line:
            line = line[:-2]
        # Remove ""
        line = line.replace('"', '')
        return line


def create_pot():
    args = f'python {pygettext} -p locale -d {APP_NAME} {MODULES}'
    print('Calling: ' + str(args))
    call(args, cwd=current_modules_dir)

    """
    # Rewrite as utf-8
    with open(f'{APP_NAME}.pot', 'r') as f_in:
        content = f_in.readlines()
    with open(f'{APP_NAME}.pot', 'w', encoding=ENCODING_VAL) as f_out:
        f_out.writelines(content)
    """


def create_mo():
    args = f'python {msgfmt} -o en/LC_MESSAGES/{APP_NAME}.mo en/LC_MESSAGES/{APP_NAME}'
    print('Calling: ' + str(args))
    call(args, cwd=os.path.join(current_modules_dir, 'locale'))

    args = f'python {msgfmt} -o de/LC_MESSAGES/{APP_NAME}.mo de/LC_MESSAGES/{APP_NAME}'
    print('Calling: ' + str(args))
    call(args, cwd=os.path.join(current_modules_dir, 'locale'))


def main():
    print('\nChoose an action:\n0 - Create pot template file\n1 - Update en po file and keep existing translations'
          '\n2 - Create mo binary files for de+en')
    choice = input('Your choice: ')

    if choice not in ['2', '1', '0']:
        print('Invalid choice.')
        main()

    if choice == '0':
        create_pot()

    if choice == '1':
        cp = CreatePo()
        cp.create_updated_en_po()
        cp.update_po_de()

    if choice == '2':
        create_mo()


if __name__ == '__main__':
    main()
