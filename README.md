# ClickRec_60

![OS](https://img.shields.io/badge/platform-Windows%2010%2F11_Only-green)
![Python Version](https://img.shields.io/badge/python-3.12.10-pink)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Release](https://img.shields.io/github/v/release/ClickMouseStudio/ClickRec_60)
![Last Commit](https://img.shields.io/github/last-commit/ClickMouseStudio/ClickRec_60)

ClickRec_60: A smart near-infrared mouse recording app designed for capturing videos at predefined durations—part of the ClickMouseStudio project.

<img src="imgs\logo.png" alt="Logo" width="400">

ClickRec_60 は、近赤外線撮影に対応したマウスの録画アプリです。ClickMouseStudio プロジェクトの一環として開発されました。

## 特長

- あらかじめ秒数で指定した録画時間に達すると自動で録画を停止するので、実験用途や観察用途において効率的な映像収集ができます。
- 近赤外線撮影時にグレースケールモードを有効にすると、すべてのチャンネルをグレースケール変換して録画します。不要なカラーノイズが、これによって除外されます。

## 動作条件

- OS : Windows10/11
- CPU: Intel 13th 以降
- RAM: 16GB 以上
- GPU: Intel iGPU
  > Intel の QSV を録画用のエンコーダーとして使用しているので、Intel 専用となっています。

## 使い方

1. アプリを起動します。

1. 使用するカメラを選択します（近赤外線カメラまたは Web カメラ）。

1. 録画時間を秒単位で指定します。

1. プレビューを開始します。

1. 録画開始ボタンをクリックすると、指定時間の録画が自動で行われます。

1. 録画が終了すると、動画ファイルが自動的に保存されます。

## 使用ライブラリとライセンス

- OpenCV : Apache License 2.0
- VidGear : Apache License 2.0
- FFmpeg : LGPL v2.1 or later（https://ffmpeg.org）

FFmpeg のバイナリ（ffmpeg.exe）は以下のサイトからダウンロードしたものを同梱しています：
https://www.gyan.dev/ffmpeg/builds/

改変は加えておらず、そのままの形で配布しています。
