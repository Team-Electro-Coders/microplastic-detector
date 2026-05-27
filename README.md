# SIH_Microplastic_Detector_by_Team_Electro_Coders

Welcome to the repository for the **Microplastic Detector Project**, developed by Team Electro Coders!

This repository contains three distinct versions of our real-time microplastic detection system, evolving from a basic proof-of-concept using an Arduino to an advanced, web-enabled system utilizing an ESP32 microcontroller.

---

## Project Overview

The core goal of this project is to create a real-time system that combines **computer vision (OpenCV)** with embedded hardware (Arduino/ESP32) to automatically identify and alert users about microplastic particles in a video stream.

---

## Repository Structure

The project's evolution is documented and implemented across three version folders:

| Folder | Version | Core Hardware | Key Focus |
| :--- | :--- | :--- | :--- |
| **MicroPlastic\_Detector\_V1.0** | **V1.0 (Basic)** | Arduino Uno | Simple real-time detection and LCD status display via serial communication. |
| **MicroPlastic\_Detector\_V2.0** | **V2.0 (Complete)** | Arduino Uno | Enhanced system with **Machine Learning (TensorFlow)** for particle type classification and a comprehensive calibration and data collection workflow. |
| **MicroPlastic\_Detector\_V3.0** | **V3.0 (Enhanced/Web)** | ESP32 DevKit | Hybrid system featuring Wi-Fi connectivity, a **live web dashboard (Flask)**, data logging, and scale calibration, using the ESP32 for local control and the PC for heavy processing. |

---

## 🛠️ Version Summaries & Features

### 1. MicroPlastic\_Detector\_V1.0 (Basic)

This is the initial, straightforward implementation focusing on proving the concept of computer vision-based detection communicating with embedded hardware.

| Component | Technology/Hardware | Function |
| :--- | :--- | :--- |
| **Detection** | Python, OpenCV | [cite_start]Detects bright particles (simulating microplastics) using image processing (grayscale, blur, thresholding, contour detection). [cite: 4, 5, 95, 97, 99, 100, 101] |
| **Hardware** | Arduino Uno, 16x2 LCD | [cite_start]Receives status via **Serial communication** and displays "Detected! :)" or "Clean :)" on the LCD. [cite: 2, 4, 5, 104] |
| **Alert** | LCD Display | [cite_start]Real-time status update based on the particle count exceeding a configurable threshold (`PARTICLE_THRESHOLD`). [cite: 65, 80, 81, 139] |
| **Customization** | Python Script | [cite_start]Sensitivity can be adjusted via `PARTICLE_THRESHOLD` and area thresholds in the contour detection code. [cite: 65, 84, 87] |

---

### 2. MicroPlastic\_Detector\_V2.0 (Complete Implementation)

Version 2.0 transforms the basic detector into a comprehensive, research-ready system by integrating machine learning for microplastic *type classification* (e.g., fiber, fragment, bead) and a structured calibration process.

| Feature | Technologies Used | Benefit |
| :--- | :--- | :--- |
| **Classification** | **TensorFlow**, **Keras** | [cite_start]Trains a model (`train_type_classifier.py`) to categorize detected particles into types like **fiber**, **fragment**, **film**, and **bead**. [cite: 473, 489, 512, 513, 514, 515, 586] |
| **Enhanced Files** | Python Scripts (e.g., `final_detector.py`, `calibrate_concentration.py`) | [cite_start]Includes enhanced scripts for detection, training, collection, and advanced concentration **calibration** for scientific validation. [cite: 538, 539, 540, 541, 602, 603] |
| **Data Workflow** | `dataset/` and `logs/` folders | [cite_start]Structured process for manual sample collection, labeling, model training, and saving results/logs. [cite: 509, 532, 565, 570] |
| **Hardware** | Arduino Uno, 16x2 LCD | [cite_start]Maintains the reliable serial communication interface for real-time status display. [cite: 435, 436] |

---

### 3. MicroPlastic\_Detector\_V3.0 (Enhanced/Web)

This version introduces an **ESP32** for connectivity and a web interface, moving towards a more modern, accessible, and data-focused platform. The Arduino serial communication is replaced with a robust Wi-Fi communication protocol.

| Feature | Technologies/Components | Benefit |
| :--- | :--- | :--- |
| **Hardware** | **ESP32 DevKit**, **I2C LCD** | [cite_start]ESP32 handles Wi-Fi, local control, and a simpler I2C LCD, improving portability and power efficiency compared to Arduino's direct serial connection. [cite: 151, 158, 201, 202, 396] |
| **Web Interface** | **Flask Web Server** | [cite_start]Provides a **Live web dashboard** at `http://localhost:5000` with real-time video, statistics, charts, and particle size histograms. [cite: 154, 179, 293, 323, 324, 325] |
| **Data Management** | CSV Logging, REST API | [cite_start]Supports automatic **CSV data logging and export** (`data_logger.py`) and uses API endpoints for fetching stats and history. [cite: 155, 184, 347, 352, 355] |
| **Calibration** | Scale Calibration Mode | [cite_start]Offers a dedicated calibration mode (`python main.py --calibrate`) to automatically calculate the pixel-to-millimeter scale factor for accurate particle sizing. [cite: 159, 273, 309, 311, 316] |
| **Configuration** | `config.json` | [cite_start]Centralized, easy-to-edit JSON file for configuring ESP32 connection, camera settings, and detection parameters. [cite: 164, 257] |

---

## ⚙️ How to Get Started

To begin working with any version, navigate to the respective folder and refer to its internal documentation (or the full PDF guides provided) for detailed setup and usage instructions.

1.  **Select a Version:** Choose the folder corresponding to the system you wish to set up (V1.0, V2.0, or V3.0).
2.  **Review Requirements:** Check the **Hardware** and **Software Requirements** section in the version's documentation.
3.  **Setup Environment:** Install the required Python packages (e.g., OpenCV, NumPy, PySerial) and set up the Arduino/ESP32 IDE with necessary libraries.
4.  **Configure & Run:**
    * **V1.0/V2.0:** Update `VIDEO_SOURCE` and `ARDUINO_PORT` in the Python script (`final_detector.py`).
    * **V3.0:** Edit the settings in `config.json`.
    * Run the main Python script.

### Example Installation (V1.0 - Python Dependencies):

```bash
# Recommended for V1.0 - also useful as a base for V2.0/V3.0
pip install opencv-python numpy pyserial
