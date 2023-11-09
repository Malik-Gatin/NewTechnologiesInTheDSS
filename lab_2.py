import os
import requests
import csv
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
from datetime import datetime
import time
from urllib.parse import urlparse, parse_qs

IMAGES_FIELDS = ['date', 'image_url', 'file_name']
DIRECTORY =  os.path.join("dataset")

# Настройка веб-драйвера
def configure_webdriver():
    # Настройки браузера (headless режим)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    return webdriver.Chrome(options=options)

# Получение значения параметра запроса из URL
def get_query_parameter(url, parameter_name):
    parsed_url = urlparse(url)
    query_parameters = parse_qs(parsed_url.query)
    return query_parameters.get(parameter_name, [None])[0]

# Ожидание загрузки элементов на странице
def wait_for_element(driver, selector):
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    except Exception as e:
        logging.error(f"Ошибка ожидания элементов: {str(e)}")

# Создание папки для класса и файла CSV, если они не существуют
def create_class_directory(class_name: str, csv_name:str = ""):
    try:
        # Создаем папку для класса, если она не существует
        class_dir = os.path.join("dataset", class_name)
        if not os.path.exists(class_dir):
            os.makedirs(class_dir)
            logging.info(f"Создана папка {class_name}")
        else:
            logging.info(f"Папка {class_name} уже существует")

        # Создаем файл CSV для класса, если он не существует
        if(csv_name!=""):
            csv_file_path = os.path.join(class_dir, f"{csv_name}.csv")
        else:
            csv_file_path = os.path.join(class_dir, f"{class_name}.csv")
        if not os.path.exists(csv_file_path):
            with open(csv_file_path, mode='w', newline='') as file:
                csv_writer = csv.writer(file)
            logging.info(f"Создан файл CSV для {class_name}")
        else:
            logging.info(f"Файл CSV уже существует для {class_name}")
    except Exception as e:
        logging.error(f"Ошибка при создании файла или папки {class_name}: {str(e)}")    

# создание пути до файла .csv
def create_file_path(class_n:str, full_size:bool) -> str:
    class_name = class_n
    if(full_size):
        class_name += "_full-size"
    else:
        class_name += "_thumb"
    return os.path.join("dataset", class_name, f"{class_name}.csv")

# запись в .csv файл
def write_csv_file(path: str, data: list) -> None:
    mode = 'w' if not os.path.exists(path) else 'a'
    with open(path, mode, newline='') as csv_file:
      csv_writer = csv.writer(csv_file)
      csv_writer.writerow(data)

# Загрузка изображения
def download_image(img_url, img_path):
    max_retry = 2  # Максимальное количество попыток загрузки изображения
    for _ in range(max_retry):
        try:
            img_extension = img_url.split(".")[-1]
            img_ext = "jpg" in img_extension or "thumbs" in img_extension
            if img_ext:
                img_data = requests.get(img_url).content
                with open(img_path, "wb") as img_file:
                    img_file.write(img_data)         
                return True
        except Exception as e:
            logging.warning(f"Ошибка при загрузке изображения: {str(e)}")
    logging.error(f"Не удалось загрузить изображение: {img_url}")
    return False

# Загружает изображение по указанному URL-адресу
def download_images(query, num_images=1000, full_size=False):
    class_name = query

    create_class_directory(class_name)
    driver = configure_webdriver()

    # URL для поиска изображений
    url = f"https://yandex.ru/images/search?text={query}&type=photo"
    driver.get(url)

    count = 0
    csv_file_path = create_file_path(class_name, full_size)

    write_csv_file(csv_file_path, IMAGES_FIELDS)

    while count < num_images:
        # Выбор селектора для изображения (миниатюра или полноразмерное)
        img_selector = "img.serp-item__thumb" if not full_size else "a.serp-item__link"
        wait_for_element(driver, img_selector)
        img_links = driver.find_elements(By.CSS_SELECTOR, img_selector)

        for img_link in img_links:
            if count >= num_images:
                break
            try:
                if not full_size:
                    img_url = img_link.get_attribute("src")
                else:
                    img_url = img_link.get_attribute("href")
                    img_url = get_query_parameter(img_url, "img_url")

                if ("jpg" in img_url or "thumbs" in img_url):
                    filename = f"{count:04}.jpg"
                    img_path = os.path.join("dataset", class_name, filename)

                    if download_image(img_url, img_path):
                        count += 1
                        write_csv_file(csv_file_path, [datetime.now().strftime('%Y-%m-%d'), img_url, filename])
                    logging.info(f"Uploaded image {count} for class {class_name}")
                else:
                    continue
            except Exception as e:
                pass

        # Прокручиваем страницу вниз, чтобы подгрузились новые картинки
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)
    # Завершаем сеанс браузера
    driver.quit()   
     
# проверка на существование полей в .csv файлу
def check_csv_on_valid_fields(df: pd.DataFrame, required_fields: list) -> bool:
    for field in required_fields:
        if field not in df.columns:
            return False
    return True
     
#  Читает данные из файла в формате CSV, выполняет проверку наличия необходимых полей и объединяет их в один DataFrame.
def create_data_frame_from_csv(file: list, fields: list) -> pd.DataFrame:
    df_list = []
    data = pd.read_csv(file)
      # Проверка наличия необходимых полей в данных
    if check_csv_on_valid_fields(data, fields):
        data['date'] = pd.to_datetime(data['date'])
        df_list.append(data)
    else:
        print(f'Ошибка: Файл {file} не содержит необходимых полей')
    df = pd.concat(df_list, ignore_index=True)
    return df
     
# проход по данным
def next_data(df: pd.DataFrame, index: int) -> tuple[str]:
    if index < len(df):
        return tuple(df.iloc[index]) #возвращает строки по целочисленным значениям
    return None

# ШАГ 1
# Написать скрипт, который разобъёт исходный csv файл на файл X.csv и Y.csv, 
# с одинаковым количеством строк. Первый будет содержать даты, второй - данные.

# Запись других дат в .csv файл
def write_another_dates(df: pd.DataFrame, start_date: datetime) -> pd.DataFrame:
    df['date'] = [start_date + pd.DateOffset(days=i) for i in range(len(df))]
    return df
# Разделение данных на 2 .csv файла: с датами и остальными данными
def separation_date_by_data(df: pd.DataFrame) -> None:
    df_date = df['date']
    df_data = df.drop('date', axis=1)
    create_class_directory("csv_date_by_data", "X")
    create_class_directory("csv_date_by_data", "Y")
    df_date.to_csv(os.path.join(DIRECTORY,'csv_date_by_data\\X.csv'), index=False)
    df_data.to_csv(os.path.join(DIRECTORY, 'csv_date_by_data\\Y.csv'), index=False)

# загрузка всех изображений
def download_all_images():
    # Загрузка полноразмерных изображений для классов "leopard" и "tiger"
    download_images("tiger", num_images=20, full_size=True)
    download_images("leopard", num_images=20, full_size=True)

    # Загрузка миниатюр для классов "leopard" и "tiger"
    download_images("tiger", num_images=10, full_size=False)
    download_images("leopard", num_images=100, full_size=False)

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(filename="image_download.log", level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

    try:
        #download_all_images()
        csv_file = create_file_path("tiger", True)
        df = create_data_frame_from_csv(csv_file, IMAGES_FIELDS)
        write_another_dates(df, datetime(2023, 1, 1))
        print(df)
        separation_date_by_data(df)

        print('ВЫВОД next_data() :')
        for index in range(0, len(df)):
            print(next_data(df, index))

    except Exception as e:
        logging.error(f"An error has occurred: {str(e)}")
        print(str(e))
