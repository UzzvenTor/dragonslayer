"""Локальный sync свежих отчётов Голиафа в Obsidian.

Работает только локально (не на CI). На CI отчёты коммитятся в репо как часть workflow.

Запуск:
  python sync_obsidian.py            # подтянуть git pull + скопировать недостающие .md в Obsidian
  python sync_obsidian.py --no-pull  # только копирование, без git pull

Требует в `.env`:
  OBSIDIAN_REPORT_DIR=I:/OBSIDIAN/.../daily_reports
"""
import os, sys, glob, shutil, subprocess, argparse

sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


def main(do_pull: bool):
    repo_root  = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    src_dir    = os.path.join(repo_root, 'goliath_daily', 'reports')
    dst_dir    = (os.environ.get('OBSIDIAN_REPORT_DIR') or '').strip()

    if not dst_dir:
        print('OBSIDIAN_REPORT_DIR не задан в .env — нечего делать.')
        sys.exit(1)
    if not os.path.isdir(os.path.dirname(dst_dir.rstrip('/').rstrip('\\'))):
        print(f'Родительская папка для {dst_dir} не существует — проверь путь в .env.')
        sys.exit(1)
    os.makedirs(dst_dir, exist_ok=True)

    if do_pull:
        print(f'git pull в {repo_root}...')
        r = subprocess.run(['git', '-C', repo_root, 'pull', '--ff-only'],
                           capture_output=True, text=True)
        print(r.stdout.strip() or '(no output)')
        if r.returncode != 0:
            print(f'⚠️ git pull failed:\n{r.stderr.strip()}')
            sys.exit(1)

    files = sorted(glob.glob(os.path.join(src_dir, '*.md')))
    copied = 0
    for f in files:
        name = os.path.basename(f)
        dst = os.path.join(dst_dir, name)
        if not os.path.exists(dst):
            shutil.copy(f, dst)
            print(f'  + {name}')
            copied += 1
    print(f'\nСкопировано новых файлов: {copied} (из {len(files)} всего в репо)')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-pull', action='store_true', help='Не делать git pull')
    args = ap.parse_args()
    main(do_pull=not args.no_pull)
