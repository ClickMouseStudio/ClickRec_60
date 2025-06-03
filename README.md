# ClickRec_60

![OS](https://img.shields.io/badge/platform-Windows%2010%2F11_Only-green)
![Python Version](https://img.shields.io/badge/python-3.12.10-pink)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Release](https://img.shields.io/github/v/release/ClickMouseStudio/ClickRec_60)
![Last Commit](https://img.shields.io/github/last-commit/ClickMouseStudio/ClickRec_60)


ClickRec_60: A smart near-infrared mouse recording app designed for capturing videos at predefined durations—part of the ClickMouseStudio project.

ClickRec_60 は、実験動物のマウス観察を目的に開発された録画アプリです。ClickMouseStudio プロジェクトの一環として設計されており、近赤外線カメラでの使用を前提としながらも、汎用的なWebカメラにも対応しています。

## 特長
あらかじめ秒数で指定した録画時間に達すると自動で録画を停止するので、実験用途や観察用途において効率的な映像収集ができます。

## 使い方

1. アプリを起動します。

1. 使用するカメラを選択します（近赤外線カメラまたはWebカメラ）。

1. 録画時間を秒単位で指定します。

1. プレビューを開始します。

1. 録画開始ボタンをクリックすると、指定時間の録画が自動で行われます。

1. 録画が終了すると、動画ファイルが自動的に保存されます。



## 使用ライブラリとライセンス

- OpenCV : Apache License 2.0
- VidGear : Apache License 2.0
- FFmpeg : LGPL v2.1 or later（https://ffmpeg.org）

FFmpegのバイナリ（ffmpeg.exe）は以下のサイトからダウンロードしたものを同梱しています：
https://www.gyan.dev/ffmpeg/builds/

改変は加えておらず、そのままの形で配布しています。