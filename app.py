from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import datetime
import platform
import time
import subprocess
import mimetypes

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'html', 'css', 'js', 'py', 'json', 'md', 'csv', 'xlsx'}

# Создаем папку для загрузок, если она не существует
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_directory_size(path):
    """Рассчитывает общий размер файлов в директории"""
    total_size = 0
    file_count = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp) and os.path.isfile(fp):
                total_size += os.path.getsize(fp)
                file_count += 1
    return total_size, file_count

def format_size(size_bytes):
    """Форматирует размер в байтах в удобочитаемый формат"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.1f} GB"

def get_system_info():
    """Получает информацию о системе без использования psutil"""
    info = {}
    
    # Базовая информация о системе
    info['python_version'] = platform.python_version()
    info['system'] = platform.system()
    info['node'] = platform.node()
    info['release'] = platform.release()
    
    # Информация о CPU из /proc/cpuinfo (только для Linux)
    info['cpu_cores'] = 'N/A'
    info['cpu_threads'] = 'N/A'
    info['cpu_usage'] = 'N/A'
    
    if os.path.exists('/proc/cpuinfo'):
        try:
            cpu_info = subprocess.check_output(['cat', '/proc/cpuinfo']).decode('utf-8')
            cores = set()
            threads = 0
            for line in cpu_info.split('\n'):
                if 'processor' in line:
                    threads += 1
                if 'core id' in line:
                    core_id = line.split(':')[1].strip()
                    cores.add(core_id)
            info['cpu_cores'] = str(len(cores)) if cores else '1'
            info['cpu_threads'] = str(threads)
        except:
            pass
    
    # Информация о памяти из /proc/meminfo (только для Linux)
    info['total_memory'] = 'N/A'
    info['available_memory'] = 'N/A'
    info['memory_usage'] = 'N/A'
    
    if os.path.exists('/proc/meminfo'):
        try:
            mem_info = subprocess.check_output(['cat', '/proc/meminfo']).decode('utf-8')
            total = 0
            available = 0
            for line in mem_info.split('\n'):
                if 'MemTotal' in line:
                    total = int(line.split()[1]) * 1024
                    info['total_memory'] = format_size(total)
                if 'MemAvailable' in line:
                    available = int(line.split()[1]) * 1024
                    info['available_memory'] = format_size(available)
            
            if total > 0 and available > 0:
                usage_percent = (total - available) / total * 100
                info['memory_usage'] = f"{usage_percent:.1f}%"
        except:
            pass
    
    # Информация о диске
    try:
        if platform.system() == 'Windows':
            total, used, free = shutil.disk_usage('/')
        else:
            df_output = subprocess.check_output(['df', '-h', '/']).decode('utf-8').split('\n')[1]
            parts = df_output.split()
            total = parts[1]
            free = parts[3]
            used_percent = parts[4]
            info['total_disk'] = total
            info['free_disk'] = free
            info['disk_usage'] = used_percent
    except:
        info['total_disk'] = 'N/A'
        info['free_disk'] = 'N/A'
        info['disk_usage'] = 'N/A'
    
    # Время работы системы из /proc/uptime (только для Linux)
    info['uptime'] = 'N/A'
    if os.path.exists('/proc/uptime'):
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                info['uptime'] = format_uptime(int(uptime_seconds))
        except:
            pass
    
    # IP-адрес сервера
    try:
        # Получаем IP-адрес, используя ifconfig или ip addr
        if os.name == 'nt':  # Windows
            ipconfig = subprocess.check_output(['ipconfig']).decode('utf-8', errors='ignore')
            for line in ipconfig.split('\n'):
                if 'IPv4' in line and ('192.168.' in line or '10.' in line):
                    info['ip_address'] = line.split(':')[-1].strip()
                    break
        else:  # Linux/Unix
            command = 'ip addr show' if os.path.exists('/sbin/ip') else 'ifconfig'
            try:
                netinfo = subprocess.check_output(command.split()).decode('utf-8', errors='ignore')
            except:
                # Если команда не найдена, пробуем для Termux
                try:
                    netinfo = subprocess.check_output(['ip', 'addr', 'show']).decode('utf-8', errors='ignore')
                except:
                    netinfo = ""
                    
            for line in netinfo.split('\n'):
                if 'inet ' in line and not '127.0.0.1' in line:
                    found = False
                    for prefix in ['192.168.', '10.', '172.']:
                        if prefix in line:
                            info['ip_address'] = line.split()[1].split('/')[0]
                            found = True
                            break
                    if found:
                        break
            
            # Если IP не найден, пробуем через hostname -I
            if 'ip_address' not in info:
                try:
                    ip = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip().split()[0]
                    if ip:
                        info['ip_address'] = ip
                except:
                    info['ip_address'] = 'Недоступно'
    except:
        info['ip_address'] = 'Недоступно'
    
    # Порт Flask
    info['port'] = '8080'  # Hardcoded из __main__
    
    return info

def format_uptime(seconds):
    """Форматирует время работы системы"""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m {seconds}s"

def get_file_info(file_path):
    """Получает детальную информацию о файле"""
    info = {}
    
    # Базовая информация
    info['size'] = os.path.getsize(file_path)
    info['formatted_size'] = format_size(info['size'])
    info['modified'] = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
    info['created'] = datetime.datetime.fromtimestamp(os.path.getctime(file_path))
    
    # Тип файла
    mime_type, _ = mimetypes.guess_type(file_path)
    info['mime'] = mime_type or 'application/octet-stream'
    
    # Разрешения файла
    stat_info = os.stat(file_path)
    info['permissions'] = oct(stat_info.st_mode)[-3:]
    
    return info

@app.route('/')
def index():
    # Получаем список файлов в корневой директории
    files = [f for f in os.listdir('.') if os.path.isfile(f)]
    directories = [d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith('.')]
    
    # Сортируем файлы и директории
    files.sort()
    directories.sort()
    
    # Получаем размер текущей директории и количество файлов
    dir_size, total_files = get_directory_size('.')
    formatted_size = format_size(dir_size)
    
    # Получаем детальную информацию о файлах
    file_info = {}
    for file in files:
        try:
            file_info[file] = get_file_info(file)
        except Exception as e:
            file_info[file] = {'formatted_size': '0 B', 'error': str(e)}
    
    # Получаем информацию о системе
    system_info = get_system_info()
    
    # Текущая дата и время
    now = datetime.datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%d.%m.%Y")
    current_year = now.year
    
    # Информация о платформе
    os_name = platform.system()
    if os_name == 'Linux' and 'com.termux' in os.environ.get('PREFIX', ''):
        platform_name = "Termux"
    else:
        platform_name = os_name
    
    return render_template('index.html', 
                          files=files, 
                          directories=directories, 
                          path='.',
                          total_size=formatted_size,
                          total_files=total_files,
                          file_info=file_info,
                          system_info=system_info,
                          current_time=current_time,
                          current_date=current_date,
                          current_year=current_year,
                          platform=platform_name)

@app.route('/browse/<path:subpath>')
def browse(subpath):
    # Проверка на безопасность пути
    if '..' in subpath:
        return "Доступ запрещен", 403
    
    full_path = os.path.join('.', subpath)
    if os.path.isfile(full_path):
        return send_from_directory('.', subpath)
    
    files = [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]
    directories = [d for d in os.listdir(full_path) if os.path.isdir(os.path.join(full_path, d)) and not d.startswith('.')]
    
    # Сортируем файлы и директории
    files.sort()
    directories.sort()
    
    # Получаем размер текущей директории и количество файлов
    dir_size, total_files = get_directory_size(full_path)
    formatted_size = format_size(dir_size)
    
    # Получаем детальную информацию о файлах
    file_info = {}
    for file in files:
        try:
            file_path = os.path.join(full_path, file)
            file_info[file] = get_file_info(file_path)
        except Exception as e:
            file_info[file] = {'formatted_size': '0 B', 'error': str(e)}
    
    # Получаем информацию о системе
    system_info = get_system_info()
    
    # Текущая дата и время
    now = datetime.datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%d.%m.%Y")
    current_year = now.year
    
    # Информация о платформе
    os_name = platform.system()
    if os_name == 'Linux' and 'com.termux' in os.environ.get('PREFIX', ''):
        platform_name = "Termux"
    else:
        platform_name = os_name
    
    return render_template('index.html', 
                          files=files, 
                          directories=directories, 
                          path=subpath,
                          total_size=formatted_size,
                          total_files=total_files,
                          file_info=file_info,
                          system_info=system_info,
                          current_time=current_time,
                          current_date=current_date,
                          current_year=current_year,
                          platform=platform_name)

@app.route('/upload', methods=['POST'])
def upload_file():
    # Проверяем, был ли файл отправлен
    if 'file' not in request.files:
        return redirect(request.referrer or url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        return redirect(request.referrer or url_for('index'))
    
    if file and allowed_file(file.filename):
        # Определяем директорию для загрузки в зависимости от типа файла
        filename = file.filename
        file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Если это HTML-файл, всегда загружаем в UPLOAD_FOLDER
        if file_extension == 'html':
            upload_path = app.config['UPLOAD_FOLDER']
        else:
            # Для других типов файлов используем указанный путь
            upload_path = request.form.get('path', app.config['UPLOAD_FOLDER'])
            # Проверка на безопасность пути
            if '..' in upload_path:
                return "Доступ запрещен", 403
        
        # Создаем директорию, если не существует
        os.makedirs(upload_path, exist_ok=True)
        
        # Сохраняем файл
        filepath = os.path.join(upload_path, file.filename)
        file.save(filepath)
        
        # Перенаправляем обратно
        return redirect(request.referrer or url_for('index'))
    
    return redirect(request.referrer or url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
