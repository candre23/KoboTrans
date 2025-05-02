# KCPP Subtitle Translator

A Python script to translate SubRip (.srt) subtitles using KoboldCPP as the AI backend.  This is a quick and dirty hack of https://github.com/passthesh3ll/srt-ai-translator, using gemini and some trial & error instead of actual skill or understanding.  Works well with Qwen3 models - may require tweaking for others.   Looks for KCPP running locally on port 5001.  Modify line 8 if you're using a non-standard port.

## Usage

```bash
python kobotrans.py <input SRT File> <input language code> <output language code>
```
So for example, if you wanted to translate the English subtitle file "movie.srt" into Italian, you would use

```bash
python kobotrans.py movie.srt eng ita
```
This will create a translated file "movie_ita.srt"

Available language codes: [ISO 639-2 Codes](https://www.loc.gov/standards/iso639-2/php/code_list.php)

## Dependencies

requests, json, tqdm, os, threading, pycountry, argparse, time, colorama
