# SIH2026-Z-END

# 🚆 SIH2026-Z-END

## Intelligent Railway Block Planning and Conflict-Free Scheduling System

### 📌 Project Overview

This project proposes an intelligent railway block planning and scheduling system designed to improve railway maintenance planning, reduce conflicts, and support efficient utilization of railway sections.

The system combines **data processing, machine learning, railway network visualization, optimization, and officer approval workflows** to generate efficient and conflict-free block plans.

---

## 🎯 Problem Statement

Railway maintenance activities require planned blocks on railway sections. Poor coordination between maintenance requirements, train movements, available sections, and operational constraints can result in:

* Conflicting block allocations
* Inefficient utilization of railway sections
* Delays in maintenance activities
* Manual planning overhead
* Difficulty in tracking approved and executed blocks

The proposed system aims to provide an intelligent, data-driven approach for generating optimized and conflict-free railway block plans.

---

## 💡 Proposed Solution

The system follows an end-to-end workflow:

```text
Data Sources
     ↓
Data Preprocessing
     ↓
ML Prediction
     ↓
Railway Network Graph
     ↓
Optimization
     ↓
Conflict-Free Block Plan
     ↓
Officer Approval
     ↓
Execution Tracking
```

The system analyzes railway-related data, predicts relevant requirements, represents railway sections as a network graph, and applies optimization techniques to generate feasible block plans.

---

## ✨ Key Features

* 📊 Data-driven railway block planning
* 🤖 Machine Learning based prediction
* 🚆 Railway network graph visualization
* ⚙️ Optimization of maintenance blocks
* 🚫 Conflict-free block generation
* 👨‍💼 Officer approval workflow
* 📋 Execution and audit tracking
* 📈 Dashboard-based monitoring
* 🔍 Section-wise information and status
* 📝 Audit log for important activities

---

## 🏗️ System Architecture

```
                    ┌──────────────────┐
                    │   Data Sources   │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Preprocessing    │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ ML Prediction    │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Railway Graph    │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │  Optimization    │
                    └────────┬─────────┘
                             ↓
                 ┌─────────────────────────┐
                 │ Conflict-Free Block Plan│
                 └────────────┬────────────┘
                              ↓
                    ┌──────────────────┐
                    │ Officer Approval │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Execution Track. │
                    └──────────────────┘
```

---

## 🛠️ Technologies Used

### Frontend

* React
* JavaScript / JSX
* HTML
* CSS
* Vite

### Backend

* Python
* Flask
* REST APIs

### Machine Learning

* Python
* Scikit-learn
* Pandas
* NumPy

### Data & Processing

* CSV / structured datasets
* Data preprocessing
* Mock data generation

### Development & Version Control

* Git
* GitHub
* Visual Studio Code

---

## 📁 Project Structure

```
SIH2026-Z-END/
│
├── backend/
│   ├── auth/
│   ├── models/
│   ├── routes/
│   └── main.py
│
├── data/
│   └── mock/
│
├── frontend_react/
│   └── frontend/
│       ├── src/
│       │   ├── components/
│       │   │   ├── Login.jsx
│       │   │   ├── Dashboard.jsx
│       │   │   ├── DefectsSummary.jsx
│       │   │   ├── NetworkGraph.jsx
│       │   │   ├── PlansGrid.jsx
│       │   │   ├── SectionsTable.jsx
│       │   │   └── AuditLog.jsx
│       │   │
│       │   ├── App.jsx
│       │   ├── main.jsx
│       │   └── index.css
│       │
│       ├── index.html
│       ├── package.json
│       ├── package-lock.json
│       └── SETUP.md
│
├── database/
├── doc/
├── generate_mock_data.py
├── requirements.txt
└── README.md
```

---

## ⚙️ Frontend Setup

Navigate to the frontend directory:

```bash
cd frontend_react/frontend
```

Install the required dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

The application will then be available through the local development URL displayed in the terminal.

---

## ⚙️ Backend Setup

Navigate to the project directory:

```bash
cd SIH2026-Z-END
```

Create and activate a Python virtual environment:

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Start the backend using the project's configured Flask entry point.

---

## 🔄 System Workflow

### 1. Data Collection

Railway-related operational and maintenance data is collected from available datasets and project data sources.

### 2. Data Preprocessing

The collected data is cleaned, transformed, and prepared for prediction and optimization.

### 3. ML Prediction

Machine learning techniques are used to identify or predict relevant railway requirements from the available data.

### 4. Railway Network Representation

Railway sections and their relationships are represented using a network graph.

### 5. Optimization

The system considers railway constraints and requirements to generate an efficient allocation of maintenance blocks.

### 6. Conflict-Free Planning

Potential conflicts between planned blocks are identified and avoided while generating the final plan.

### 7. Officer Approval

The generated plan can be reviewed by the authorized railway officer before execution.

### 8. Execution Tracking

Approved activities can be tracked through the system, with important actions recorded through the audit log.

---

## 👥 Team

**SIH 2026 Team – SIET**

* Bharathraj
* Dharsni
* Gopikrishnan
* Hanushree
* Karthikprakash
* Madhan Kumar

---

## 🚀 Future Enhancements

* Real-time railway data integration
* Advanced predictive maintenance
* Real-time train movement integration
* Improved optimization algorithms
* Automated conflict detection
* Role-based access control
* Real-time notifications
* Cloud deployment
* Mobile support
* Advanced analytics and reporting

---

## 📌 Project Status

The project is currently under active development as part of **Smart India Hackathon (SIH) 2026**.

The frontend, backend, data processing, machine learning, railway graph, and optimization modules are being developed and integrated incrementally.

---

## 📄 License

This project is developed for educational and hackathon purposes as part of SIH 2026.
