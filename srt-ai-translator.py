from g4f.client import Client
from g4f.Provider import Blackbox
from tqdm import tqdm
import os, threading, json, pycountry, argparse, time

def srt_to_dict(file_path):
    subtitles = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        if lines[i].strip().isdigit():
            subtitle = {}
            subtitle['id'] = lines[i].strip()
            i += 1
            subtitle['time-start'], subtitle['time-end'] = lines[i].strip().split(' --> ')
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            subtitle['text'] = '\n'.join(text_lines)
            subtitle['translated'] = ''
            subtitles.append(subtitle)
        i += 1

    return subtitles
def dict_to_srt(subtitles, output_file_path):
    with open(output_file_path, 'w', encoding='utf-8') as f:
        for subtitle in subtitles:
            f.write(subtitle['id'] + '\n')
            f.write(subtitle['time-start'] + ' --> ' + subtitle['time-end'] + '\n')
            f.write(subtitle['translated'] + '\n\n')
def translate_subtitle(client, subtitle, input_lang, output_lang, pbar):
    max_retries = 2
    retries = 0
    while retries <= max_retries:
        try:
            response = client.chat.completions.create(
                model="DeepSeek-V3",
                messages=[{"role": "user", "content": f"Translate the following sentence from {input_lang} to {output_lang}, write only the translated sentence: {subtitle['text']}"}],
                web_search=False
            )
            subtitle['translated'] = response.choices[0].message.content
            pbar.update(1)
            return  # Translation successful, exit the function
        except Exception as e:
            print(f"ERR: sub {subtitle['id']} -> {e}, retry {retries + 1}/{max_retries + 1}")
            retries += 1
            if retries <= max_retries:
                time.sleep(5)  # Wait for a short time before retrying
            else:
                subtitle['translated'] = "! TRANSLATION ERROR !"
                pbar.update(1)
                return  # Max retries reached, exit the function

def check_language(lang_code):
    # https://www.loc.gov/standards/iso639-2/php/code_list.php
    try:
        language = pycountry.languages.get(alpha_2=lang_code) or pycountry.languages.get(alpha_3=lang_code)
        return language.name.upper()
    except KeyError:
        return False

def main():
    # ARGUMENTS
    parser = argparse.ArgumentParser(description="translate a SRT file using gpt4free.")
    parser.add_argument("input_file", help="input path for the .srt file")
    parser.add_argument("input_lang", help="input language")
    parser.add_argument("output_lang", help="output language")
    parser.add_argument("output_file", help="output path for the .srt file")

    args = parser.parse_args()
    input_file = args.input_file
    input_lang = check_language(args.input_lang)
    output_lang = check_language(args.output_lang)
    output_file = args.output_file
    
    # ERROR CHECK
    if not os.path.exists(input_file):
        print("ERR: input file not found.")
        return 1
    if input_lang == False:
        print("ERR: invalid input language.")
        return 1
    if output_lang == False:
        print("ERR: invalid output language.")
        return 1

    # SUMMARY
    print(f"Translating {input_file} [{input_lang}->{output_lang}]")

    # PARAMETERS
    file_name, file_ext = os.path.splitext(input_file)
    subtitles_list = srt_to_dict(input_file)
    client = Client(provider=Blackbox)

    # TRANSLATION
    threads = []
    threads_number = 500
    with tqdm(total=len(subtitles_list), desc=f"Translating ({threads_number} threads)") as pbar:
        for subtitle in subtitles_list:
            thread = threading.Thread(target=translate_subtitle, args=(client,subtitle,input_lang,output_lang,pbar))
            threads.append(thread)
            thread.start()

            # threads_number + 1 for the main thread
            while threading.active_count() > threads_number + 1:
                pass

        # wait threads termination
        for thread in threads:
            thread.join()
            

    # FINAL SAVE
    dict_to_srt(subtitles_list, output_file)

if __name__ == "__main__":
    main()