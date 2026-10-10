"""Align ALP portal ownership checks with the existing integration guard."""
import argparse
from pathlib import Path
import shutil
import subprocess
from datetime import datetime

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--backup',type=Path,required=True)
args=parser.parse_args()
if str(args.root)!='/home/alp/public_html/siacat':raise SystemExit('Unexpected ALP root')
paths=['abissol/bootstrap.php','abissol/liquidaciones.php','abissol/index.php']
changes={}
for name in paths:
    path=args.root/name
    text=path.read_text(encoding='utf-8-sig')
    if name.endswith('bootstrap.php'):
        start=text.index('function alp_abissol_row_visible_for_current_user(')
        end=text.index('\n}',start)+2
        replacement='''function alp_abissol_row_visible_for_current_user(array $row)
{
    global $abissolRole, $abissolUserId;
    return alp_int_user_can_access($abissolRole, $abissolUserId,
        $row['external_emitter_id'] ?? 0, $row['external_responsible_id'] ?? 0);
}'''
        text=text[:start]+replacement+text[end:]
    else:
        text=text.replace('[0, 1, 2, 3], true)', '[0, 1, 2, 3, 4], true)',1)
    changes[path]=text
args.backup.mkdir(parents=True,exist_ok=True)
for path,text in changes.items():
    backup=args.backup/path.name
    if not backup.exists():shutil.copy2(path,backup)
    staged=path.with_suffix('.php.scope-staged')
    staged.write_text(text,encoding='utf-8')
    subprocess.run(['/opt/cpanel/ea-php83/root/usr/bin/php','-l',str(staged)],check=True)
    staged.unlink()
for path,text in changes.items():
    path.write_text(text,encoding='utf-8')
    print('Updated',path.name)
