import requests # Added for making HTTP requests
import json     # Added for handling JSON data
from tqdm import tqdm
import os, threading, pycountry, argparse, time
from colorama import init, Fore

# KoboldCPP API endpoint
KOBOLDCPP_API_URL = "http://localhost:5001/api/v1/generate"

def srt_to_dict(file_path):
    subtitles = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        # Ensure the line is a digit before processing subtitle block
        if lines[i].strip().isdigit():
            subtitle = {}
            subtitle['id'] = lines[i].strip()
            i += 1
            # Check if the next line contains the timecodes
            if i < len(lines) and '-->' in lines[i]:
                subtitle['time-start'], subtitle['time-end'] = lines[i].strip().split(' --> ')
                i += 1
                text_lines = []
                # Gather text lines until a blank line or end of file
                while i < len(lines) and lines[i].strip():
                    text_lines.append(lines[i].strip())
                    i += 1
                subtitle['text'] = '\n'.join(text_lines)
                subtitle['translated'] = ''
                subtitles.append(subtitle)
            else:
                # Skip malformed entry if timecodes are missing
                # print(f"{Fore.YELLOW}WARN: Malformed subtitle entry near ID {subtitle['id']}. Skipping.{Fore.RESET}")
                while i < len(lines) and lines[i].strip(): # Skip potential text lines
                    i += 1
        # Move to the next line (handles blank lines between entries)
        i += 1
    return subtitles

def dict_to_srt(subtitles, output_file_path):
    with open(output_file_path, 'w', encoding='utf-8') as f:
        for subtitle in subtitles:
            f.write(subtitle['id'] + '\n')
            f.write(subtitle['time-start'] + ' --> ' + subtitle['time-end'] + '\n')
            f.write(subtitle['translated'] + '\n\n')

# Modified translate_subtitle function to use KoboldCPP API
def translate_subtitle(subtitle, input_lang, output_lang, pbar):
    max_retries = 2
    retries = 0
    prompt = f"Translate the following sentence from {input_lang} to {output_lang}, write only the translated sentence: {subtitle['text']} </think>"

    # Parameters for KoboldCPP API (adjust as needed)
    payload = {
        "prompt": prompt,
        "max_context_length": 2048, # Adjust based on your model/KoboldCPP settings
        "max_length": 200,        # Max tokens for the translated output
        "temperature": 0.4,
        "top_k": 40,
        # Add other parameters supported by KoboldCPP API if needed
        # "rep_pen": 1.1,
        # "top_p": 0.9,
    }

    headers = {
        "Content-Type": "application/json"
    }

    while retries <= max_retries:
        try:
            # Send POST request to KoboldCPP API
            response = requests.post(KOBOLDCPP_API_URL, headers=headers, json=payload, timeout=60) # Added timeout
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            result = response.json()

            # Extract the translated text (structure might vary slightly based on KoboldCPP version/settings)
            if result and 'results' in result and len(result['results']) > 0 and 'text' in result['results'][0]:
                translated_text = result['results'][0]['text'].strip()
                # Sometimes models might add the prompt or extra text, attempt to clean
                if translated_text.startswith(prompt):
                     translated_text = translated_text[len(prompt):].strip()
                # Basic cleaning if model repeats input text structure (adjust if needed)
                if f"{output_lang}:" in translated_text:
                     translated_text = translated_text.split(f"{output_lang}:", 1)[-1].strip()

                subtitle['translated'] = translated_text
            else:
                 raise ValueError("Unexpected response format from KoboldCPP API")

            pbar.update(1)
            return # Translation successful

        except requests.exceptions.RequestException as e:
            print(f"{Fore.YELLOW}ERR: Network/API error for sub {subtitle['id']} -> {e}, {Fore.GREEN}retry {retries + 1}/{max_retries + 1}{Fore.RESET}")
            retries += 1
            if retries <= max_retries:
                time.sleep(5) # Wait before retrying
            else:
                subtitle['translated'] = "! API/NETWORK ERROR !"
                pbar.update(1)
                return # Max retries reached
        except Exception as e:
            print(f"{Fore.YELLOW}ERR: Sub {subtitle['id']} processing error -> {e}, {Fore.GREEN}retry {retries + 1}/{max_retries + 1}{Fore.RESET}")
            retries += 1
            if retries <= max_retries:
                time.sleep(2)
            else:
                subtitle['translated'] = "! TRANSLATION ERROR !"
                pbar.update(1)
                return # Max retries reached

def check_language(lang_code):
    # https://www.loc.gov/standards/iso639-2/php/code_list.php
    try:
        # Try matching alpha_2 (e.g., 'en')
        language = pycountry.languages.get(alpha_2=lang_code.lower())
        if language:
            return language.name # Return full name like 'English'

        # Try matching alpha_3 (e.g., 'eng') if alpha_2 failed
        language = pycountry.languages.get(alpha_3=lang_code.lower())
        if language:
            return language.name # Return full name like 'English'

        # Try matching by name (case-insensitive) if codes failed
        language = pycountry.languages.get(name=lang_code.title())
        if language:
            return language.name

        return False # Return False if no match found
    except Exception: # Catch potential errors during lookup
        return False


def main():
    # COLORAMA SETUP
    init(autoreset=True)

    # ARGUMENTS
    parser = argparse.ArgumentParser(description="Translate a SRT file using a local KoboldCPP instance.")
    parser.add_argument("input_file", help="Input path for the .srt file")
    parser.add_argument("input_lang", help="Input language (full name or iso639 code): English, French, eng, fre...")
    parser.add_argument("output_lang", help="Output language (full name or iso639 code): English, French, eng, fre...")
    parser.add_argument("-o", "--output_file", help="Custom output path for the .srt file")
    parser.add_argument("-t", "--threads", type=int, help="Number of parallel translation threads", default=5) # Reduced default threads

    args = parser.parse_args()
    input_file = os.path.abspath(args.input_file)
    input_lang_name = check_language(args.input_lang)
    output_lang_name = check_language(args.output_lang)

    if args.output_file is None:
        nome_base, estensione = os.path.splitext(input_file)
        # Use language codes for filename if available, otherwise use input strings
        out_lang_code = args.output_lang # Default to user input
        try:
            lang_obj = pycountry.languages.get(name=output_lang_name) if output_lang_name else None
            if lang_obj and hasattr(lang_obj, 'alpha_2'):
                 out_lang_code = lang_obj.alpha_2 # Prefer 2-letter code
            elif lang_obj and hasattr(lang_obj, 'alpha_3'):
                 out_lang_code = lang_obj.alpha_3 # Fallback to 3-letter code
        except Exception:
            pass # Keep original input if lookup fails
        output_file = f"{nome_base}_{out_lang_code}{estensione}"
    else:
        # Ensure output path is absolute if provided
        output_file = os.path.abspath(args.output_file)


    threads_number = args.threads

    # ERROR CHECK
    if not os.path.exists(input_file):
        print(f"{Fore.RED}ERR: Input file not found: {input_file}{Fore.RESET}")
        return 1
    if not input_lang_name:
        print(f"{Fore.RED}ERR: Invalid input language '{args.input_lang}'. Use full name or ISO 639 code (e.g., English, French, eng, fre).{Fore.RESET}")
        return 1
    if not output_lang_name:
        print(f"{Fore.RED}ERR: Invalid output language '{args.output_lang}'. Use full name or ISO 639 code.{Fore.RESET}")
        return 1
    if not (isinstance(threads_number, int) and threads_number > 0):
        print(f"{Fore.RED}ERR: Invalid threads value. Must be a positive integer.{Fore.RESET}")
        return 1

    # SUMMARY
    print(f"Input File:  {Fore.BLUE}{input_file}{Fore.RESET}")
    print(f"Output File: {Fore.BLUE}{output_file}{Fore.RESET}")
    print(f"Languages:   {Fore.GREEN}{input_lang_name}{Fore.RESET} -> {Fore.GREEN}{output_lang_name}{Fore.RESET}")
    print(f"Threads:     {Fore.YELLOW}{threads_number}{Fore.RESET}")


    # PARAMETERS
    subtitles_list = srt_to_dict(input_file)
    if not subtitles_list:
         print(f"{Fore.RED}ERR: Could not parse any subtitles from the input file. Is it a valid SRT?{Fore.RESET}")
         return 1

    # REMOVED g4f client initialization

    # TRANSLATION
    threads = []
    print(f"\nStarting translation for {len(subtitles_list)} subtitles...")
    with tqdm(total=len(subtitles_list), desc=f"Translating ({Fore.YELLOW}{threads_number} threads{Fore.RESET})", unit="sub") as pbar:
        active_threads = []
        subtitle_index = 0
        while subtitle_index < len(subtitles_list) or active_threads:
            # Start new threads if below the limit and subtitles remain
            while len(active_threads) < threads_number and subtitle_index < len(subtitles_list):
                subtitle = subtitles_list[subtitle_index]
                # Pass arguments without the client
                thread = threading.Thread(target=translate_subtitle, args=(subtitle, input_lang_name, output_lang_name, pbar))
                thread.start()
                active_threads.append(thread)
                subtitle_index += 1

            # Clean up finished threads
            finished_threads = []
            for thread in active_threads:
                if not thread.is_alive():
                    thread.join() # Ensure thread resources are released
                    finished_threads.append(thread)

            active_threads = [t for t in active_threads if t not in finished_threads]

            # Small sleep to prevent busy-waiting
            if len(active_threads) >= threads_number or subtitle_index == len(subtitles_list):
                 time.sleep(0.1)


    # FINAL SAVE
    print(f"\nTranslation complete. Saving to {Fore.BLUE}{output_file}{Fore.RESET}")
    dict_to_srt(subtitles_list, output_file)
    print(f"{Fore.GREEN}Successfully saved translated SRT.{Fore.RESET}")

if __name__ == "__main__":
    main()