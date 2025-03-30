# AI Subtitle Translator

A Python script to translates SubRip (.srt) subtitle files using AI (g4f) in seconds.

## Description

The script takes an input .srt file, translates the subtitle text from a specified input language to an output language using an AI, and saves the translated subtitles to a new .srt file. It utilizes `g4f` for AI model interaction.

## Dependencies

1. Generate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```
2. Install dependences
```bash
pip install g4f\[all\] argparse pycountry tqdm
```
## Usage
```bash
python srt-ai-translator.py input.srt eng ita output.srt
```
Available languages: [ISO 639-2 Codes](https://www.loc.gov/standards/iso639-2/php/code_list.php)

![image](https://i.postimg.cc/zvgCw5MK/out.gif)