import json
import os

def generate():
    problems = []
    
    # 1. Mechatronik & Regelungstechnik (1-20)
    problems.append({
        "id": "1", "topic": "PID-Regler Ziegler-Nichols",
        "query": "Erkläre das Ziegler-Nichols Einstellverfahren für PID-Regler anhand der Sprungantwort und der Dauerschwingmethode mit mathematischen Formeln."
    })
    problems.append({
        "id": "2", "topic": "LQR-Zustandsraumregelung",
        "query": "Herleitung des Linear-Quadratischen Reglers (LQR) für ein inverses Pendel. Definiere die Zustandsraummatrizen A, B, C, D und die Kostenmatrizen Q und R."
    })
    problems.append({
        "id": "3", "topic": "Erweiterter Kalman-Filter (EKF)",
        "query": "Mathematische Formulierung eines EKF zur Sensordatenfusion von IMU (Beschleunigung, Gyroskop) und GPS für autonome Roboter-Navigation."
    })
    problems.append({
        "id": "4", "topic": "Feldorientierte Regelung (FOC)",
        "query": "Erkläre die feldorientierte Regelung (FOC) für permanenterregte Synchronmotoren (PMSM) inklusive Park- und Clarke-Transformationen."
    })
    problems.append({
        "id": "5", "topic": "CAN-Bus Störungsanalyse",
        "query": "Diagnose-Protokoll zur Erkennung und Behebung von CAN-Bus-Fehlern (Error Frames, Stuff Errors, Bit Errors) in mechatronischen Systemen."
    })
    problems.append({
        "id": "6", "topic": "Roboter-Kinematik (Denavit-Hartenberg)",
        "query": "Berechnung der Vorwärtskinematik eines 6-Achs-Knickarmroboters unter Verwendung der Denavit-Hartenberg (DH) Parameter."
    })
    problems.append({
        "id": "7", "topic": "Schrittmotor-Resonanzdämpfung",
        "query": "Strategien zur elektronischen Dämpfung von mechanischen Resonanzen bei Schrittmotoren im Mikroschritt-Betrieb."
    })
    problems.append({
        "id": "8", "topic": "Hydraulische Proportionalventile",
        "query": "Modellbildung und Linearisierung der Durchfluss-Kennlinie eines elektrohydraulischen Proportionalventils."
    })
    problems.append({
        "id": "9", "topic": "Anti-Windup Strategien",
        "query": "Implementierung eines Anti-Windup-Algorithmus (Back-Calculation vs. Conditional Integration) zur Vermeidung von Stellbegrenzungseffekten bei PID-Reglern."
    })
    problems.append({
        "id": "10", "topic": "Zustandsbeobachter (Luenberger)",
        "query": "Entwurf eines Luenberger-Beobachters zur Schätzung nicht messbarer Zustände eines mechatronischen Systems (z.B. Motordrehmoment)."
    })
    problems.append({
        "id": "11", "topic": "Modale Analyse & Schwingungsdämpfung",
        "query": "Methoden zur Reduzierung von Strukturschwingungen an Roboterarmen mittels aktiver piezoelektrischer Dämpfer."
    })
    problems.append({
        "id": "12", "topic": "H-Unendlich-Regelung",
        "query": "Robuster Entwurf eines H-Unendlich-Reglers zur Störgrößenkompensation bei unsicheren Streckenparametern."
    })
    problems.append({
        "id": "13", "topic": "Pneumatische Positioniersysteme",
        "query": "Regelungskonzepte für die hochpräzise Positionierung von doppeltwirkenden Pneumatikzylindern unter Berücksichtigung von Haftreibung."
    })
    problems.append({
        "id": "14", "topic": "Echtzeit-Ethernet (EtherCAT)",
        "query": "Architektur und Funktionsweise des Distributed-Clocks (DC) Mechanismus zur hochpräzisen Synchronisation in EtherCAT-Netzwerken."
    })
    problems.append({
        "id": "15", "topic": "Gleitschutzregelung (ABS)",
        "query": "Regelungsalgorithmus für eine mechatronische Gleitschutzregelung bei Schienenfahrzeugen unter Verwendung von Haftwert-Schätzern."
    })
    problems.append({
        "id": "16", "topic": "MEMS-Sensor-Kalibrierung",
        "query": "Mathematisches Verfahren zur 6-Punkt-Kalibrierung (Offset und Skalierungsfehler) von dreiachsigen MEMS-Beschleunigungssensoren."
    })
    problems.append({
        "id": "17", "topic": "Bahnplanung (Trajektoriensynthese)",
        "query": "Synthese ruckbegrenzter Bewegungsprofile (7-Segment-Beschleunigungsprofil) für CNC- und Robotikanwendungen."
    })
    problems.append({
        "id": "18", "topic": "Batterie-Management (BMS) SOC-Schätzung",
        "query": "Vergleich von Coulomb-Counting und Extended Kalman Filter (EKF) zur präzisen Schätzung des State of Charge (SOC) in Li-Ion Akkus."
    })
    problems.append({
        "id": "19", "topic": "Druckguss-Prozessregelung",
        "query": "Closed-Loop Regelung der Kolbengeschwindigkeit in der Gießphase einer Kaltkammer-Druckgussmaschine."
    })
    problems.append({
        "id": "20", "topic": "Hardware-in-the-Loop (HIL) Testing",
        "query": "Architektur und Testabdeckung eines HIL-Prüfstands für Steuergeräte im Automobilbereich mittels Echtzeit-Simulatoren."
    })

    # 2. High-Frequency Trading & Finanzen (21-40)
    problems.append({
        "id": "21", "topic": "L3-Orderbook Aggregation",
        "query": "Entwurf einer lock-freien Datenstruktur in C++ zur performanten Aggregation von Level-3-Orderbook-Updates (Order-by-Order) mit minimaler Latenz."
    })
    problems.append({
        "id": "22", "topic": "Low-Latency WebSocket Parser",
        "query": "Implementierung eines zero-copy WebSocket-Clients in Rust zur Verarbeitung von Echtzeit-Tickedaten einer Krypto-Börse."
    })
    problems.append({
        "id": "23", "topic": "Kointegration & Paare-Handel",
        "query": "Mathematischer Ablauf eines Pairs-Trading-Algorithmus unter Verwendung des Engle-Granger-Tests und Kalman-Filter-basierter Hedge-Ratio-Berechnung."
    })
    problems.append({
        "id": "24", "topic": "Market Making Adverse Selection",
        "query": "Formulierung des Avellaneda-Stoikov-Modells für optimales Market Making unter Berücksichtigung des Inventarrisikos und asymmetrischer Information."
    })
    problems.append({
        "id": "25", "topic": "FPGA-Execution in HFT",
        "query": "Architektur eines FPGA-basierten Order-Execution-Moduls (SMC/PCIe Schnittstelle) zur Minimierung der Tick-to-Trade Latenz."
    })
    problems.append({
        "id": "26", "topic": "Order Routing Optimization",
        "query": "Mathematische Modellierung eines Smart Order Routers (SOR) zur Minimierung von Market Impact und Transaktionskosten (TCA)."
    })
    problems.append({
        "id": "27", "topic": "Volatilitäts-Arbitrage (Optionen)",
        "query": "Strategie zur Ausnutzung von Differenzen zwischen impliziter und realisierter Volatilität mittels Delta-Hedged Optionsportfolios."
    })
    problems.append({
        "id": "28", "topic": "FIX-Protokoll Parser",
        "query": "Entwurf eines ultraschnellen, binär-optimierten FIX (Financial Information eXchange) Protokoll-Parsers in C++."
    })
    problems.append({
        "id": "29", "topic": "Cross-Market Arbitrage",
        "query": "Latenzsensitive Erkennung und Ausführung von Arbitragegelegenheiten zwischen Spot- und Futures-Märkten über dezentrale Börsen."
    })
    problems.append({
        "id": "30", "topic": "Statistical Arbitrage via Ornstein-Uhlenbeck",
        "query": "Modellierung von Mean-Reverting Spreads mittels Ornstein-Uhlenbeck-Prozess zur Bestimmung optimaler Entry- und Exit-Schwellen."
    })
    problems.append({
        "id": "31", "topic": "HFT Risikomanagement (Pre-Trade)",
        "query": "Entwurf eines ultraschnellen Pre-Trade-Risikoprüfungs-Moduls (Limit-Checks, Fat-Finger-Schutz) in Hardware (FPGA/ASIC) vs. Software."
    })
    problems.append({
        "id": "32", "topic": "Order Flow Imbalance (OFI)",
        "query": "Berechnung und prädiktive Validierung des Order Flow Imbalance Indikators zur kurzfristigen Preisrichtungsvorhersage."
    })
    problems.append({
        "id": "33", "topic": "Arbitrage in fragmentierten Märkten",
        "query": "Strategien zur Kompensation von Netzwerklatenz-Asymmetrien beim Arbitrage-Handel an geografisch verteilten Börsenplätzen."
    })
    problems.append({
        "id": "34", "topic": "High-Frequency Trendfolgestrategien",
        "query": "Implementierung eines adaptiven gleitenden Durchschnitts (z.B. Kaufman's Efficiency Ratio) für Intraday-Tickdaten zur Trendidentifikation."
    })
    problems.append({
        "id": "35", "topic": "Execution Algorithmen (TWAP/VWAP)",
        "query": "Mathematische Herleitung und Code-Implementierung eines VWAP-Ausführungsalgorithmus mit dynamischer Volumenprofil-Anpassung."
    })
    problems.append({
        "id": "36", "topic": "Liquiditäts-Detektion (Iceberg Orders)",
        "query": "Heuristiken und statistische Verfahren zur Echtzeit-Erkennung von versteckten Order-Volumina (Iceberg Orders) im Orderbuch."
    })
    problems.append({
        "id": "37", "topic": "Machine Learning in HFT (Feature Engineering)",
        "query": "Feature-Engineering-Pipeline für Limit-Orderbook-Daten zur Einspeisung in ein LSTM-Netzwerk zur Mid-Price-Vorhersage."
    })
    problems.append({
        "id": "38", "topic": "Flash Crash Analyse",
        "query": "Systemische Ursachenanalyse von Flash Crashes unter Berücksichtigung von Feedback-Schleifen automatisierter HFT-Algorithmen."
    })
    problems.append({
        "id": "39", "topic": "Dark Pool Arbitrage",
        "query": "Strategien zur Interaktion mit Dark Pools (Crossing Networks) zur Minimierung von Informationsabfluss (Information Leakage)."
    })
    problems.append({
        "id": "40", "topic": "Krypto-Funding-Rate Arbitrage",
        "query": "Automatisierter Handels-Loop zur Ausnutzung von Funding-Rate-Diskrepanzen zwischen Perpetual Swaps und Spot-Positionen."
    })

    # 3. Reinforcement Learning & Simulationen (41-60)
    problems.append({
        "id": "41", "topic": "PPO in kontinuierlichen Action Spaces",
        "query": "Mathematische Formulierung und Tensorboard-Diagnose von Proximal Policy Optimization (PPO) für Robotik-Aktoren mit kontinuierlichen Stellgrößen."
    })
    problems.append({
        "id": "42", "topic": "DQN für Ressourcen-Ernte",
        "query": "Implementierung eines Deep Q-Networks (DQN) mit Double-Q-Learning zur optimalen Steuerung einer mechatronischen Ernte-Maschine."
    })
    problems.append({
        "id": "43", "topic": "Reward Shaping (Oekolopoly)",
        "query": "Entwurf einer mathematisch konsistenten Belohnungsfunktion (Reward Shaping) zur Stabilisierung eines komplexen ökologischen Simulators (Oekolopoly-Modell)."
    })
    problems.append({
        "id": "44", "topic": "Multi-Agent RL (MARL)",
        "query": "Konzepte zur kooperativen Kollisionsvermeidung einer AGV-Flotte (Automated Guided Vehicles) im Lagerbereich mittels MARL (z.B. MAPPO)."
    })
    problems.append({
        "id": "45", "topic": "Actor-Critic (SAC)",
        "query": "Implementierung von Soft Actor-Critic (SAC) zur energieeffizienten Flugstabilisierung einer Quadrokopter-Drohne."
    })
    problems.append({
        "id": "46", "topic": "Modellbasierte RL (Dyna-Q)",
        "query": "Architektur eines Dyna-Q-Frameworks zur Beschleunigung des Lernprozesses durch Integration eines gelernten Umgebungsmodells."
    })
    problems.append({
        "id": "47", "topic": "Q-Learning auf Microcontrollern",
        "query": "Speicher- und laufzeitoptimierte Implementierung eines tabellarischen Q-Learning Algorithmus in C für einen 8-Bit Mikrocontroller."
    })
    problems.append({
        "id": "48", "topic": "Explorationsstrategien (Curiosity-driven)",
        "query": "Implementierung einer neugierdebasierten Exploration (Intrinsic Curiosity Module) für RL-Agenten in spärlich belohnten Umgebungen."
    })
    problems.append({
        "id": "49", "topic": "Inverse Reinforcement Learning (IRL)",
        "query": "Verfahren des Maximum Entropy IRL zur Rekonstruktion der Belohnungsfunktion eines menschlichen Roboter-Bedieners aus Demonstrationen."
    })
    problems.append({
        "id": "50", "topic": "Offline Reinforcement Learning",
        "query": "Herausforderungen und Lösungsansätze (z.B. CQL - Conservative Q-Learning) beim Training von RL-Agenten auf statischen Datensätzen ohne Simulator-Interaktion."
    })
    problems.append({
        "id": "51", "topic": "Transfer Learning in RL",
        "query": "Strategien zum Transfer gelerner Navigations-Policies von einer Simulationsumgebung (Gazebo) auf einen realen mechatronischen Roboter (Sim-to-Real)."
    })
    problems.append({
        "id": "52", "topic": "Hierarchisches Reinforcement Learning (HRL)",
        "query": "Entwurf einer Options-Architektur zur Zerlegung einer komplexen Fertigungsaufgabe in koordinierte Sub-Tasks."
    })
    problems.append({
        "id": "53", "topic": "Safety-Constrained RL",
        "query": "Implementierung von lagrangeschen Multiplikatoren zur Einhaltung von harten Sicherheitsgrenzen (z.B. maximaler Gelenkwinkel) während des Lernens."
    })
    problems.append({
        "id": "54", "topic": "Policy Gradient Theorem",
        "query": "Mathematischer Beweis des Policy Gradient Theorems als Grundlage für REINFORCE- und Actor-Critic-Algorithmen."
    })
    problems.append({
        "id": "55", "topic": "Deep Deterministic Policy Gradient (DDPG)",
        "query": "Architektur und Hyperparameter-Tuning von DDPG zur stufenlosen Drehzahlregelung einer mechatronischen Turbine."
    })
    problems.append({
        "id": "56", "topic": "Evolutionäre Strategien vs. RL",
        "query": "Vergleich von Black-Box-Optimierung (Evolutionary Strategies) und gradientenbasiertem RL für die Fortbewegung von vierbeinigen Robotern."
    })
    problems.append({
        "id": "57", "topic": "State Abstraction in RL",
        "query": "Verfahren zur Dimensionsreduktion und Feature-Aggregation des Zustandsraums bei hochdimensionalen physikalischen Systemen."
    })
    problems.append({
        "id": "58", "topic": "Temporal Difference Learning TD(lambda)",
        "query": "Erklärung von Eligibility Traces und der mathematischen Formulierung von TD(lambda) zur schnelleren Zuweisung von Belohnungen."
    })
    problems.append({
        "id": "59", "topic": "Gym-Environment Customization",
        "query": "Schritt-für-Schritt Anleitung zur Erstellung einer maßgeschneiderten OpenAI Gym Umgebung für ein physikalisches Doppelpendel."
    })
    problems.append({
        "id": "60", "topic": "RL für adaptive PID-Parametrierung",
        "query": "Entwurf eines RL-Agenten, der im laufenden Betrieb die Kp, Ki und Kd Parameter eines PID-Reglers an variierende Lastzustände anpasst."
    })

    # 4. High-Performance Engineering & Python (61-80)
    problems.append({
        "id": "61", "topic": "Multiprocessing Shared Memory",
        "query": "Implementierung einer performanten Datenverarbeitung unter Verwendung von 'multiprocessing.shared_memory' zur Vermeidung von IPC-Latenzen."
    })
    problems.append({
        "id": "62", "topic": "Asyncio Event Loop Optimierung",
        "query": "Strategien zur Vermeidung von Event-Loop-Blockaden in asynchronen Python-Anwendungen mit hoher I/O-Last."
    })
    problems.append({
        "id": "63", "topic": "Cython & C-Extensions",
        "query": "Schritt-für-Schritt Anleitung zur Kompilierung rechenintensiver Python-Funktionen mit Cython inklusive statischer Typisierung."
    })
    problems.append({
        "id": "64", "topic": "AST-basierte Code-Injektion",
        "query": "Nutze das Python 'ast' Modul, um eine Klasse syntaktisch zu parsen, Methoden-Knoten zu modifizieren und den modifizierten Code sicher auszuführen."
    })
    problems.append({
        "id": "65", "topic": "Python Speicherdiagnose (objgraph)",
        "query": "Systematischer Debugging-Ablauf zur Erkennung von zirkulären Referenzen und Speicherlecks mittels 'objgraph' und 'tracemalloc'."
    })
    problems.append({
        "id": "66", "topic": "Lock-Free Ring Buffer in Python",
        "query": "Implementierung eines thread-sicheren, lock-freien Ringpuffers (Single-Producer, Single-Consumer) in Python."
    })
    problems.append({
        "id": "67", "topic": "GIL-Umgehung (Global Interpreter Lock)",
        "query": "Vergleich von Multiprocessing, C-Extensions (ctypes/CFFI) und Subinterpretern zur echten parallelen Thread-Ausführung in Python."
    })
    problems.append({
        "id": "68", "topic": "Python Profiling (cProfile & Line_Profiler)",
        "query": "Praktischer Leitfaden zum Auffinden von CPU-Engpässen in komplexen Python-Skripten mittels cProfile und line_profiler."
    })
    problems.append({
        "id": "69", "topic": "Zero-Copy Data Pipelines",
        "query": "Verwendung von memoryview, bytearray und numpy-Vektorisierung zum Aufbau einer zero-copy Daten-Pipeline zur Sensor-Stream-Verarbeitung."
    })
    problems.append({
        "id": "70", "topic": "Meta-Programmierung (Metaklassen)",
        "query": "Entwurf einer Python-Metaklasse zur automatischen Laufzeit- und Typenvalidierung aller registrierten mechatronischen Treiberklassen."
    })
    problems.append({
        "id": "71", "topic": "Garbage Collector Tuning in Python",
        "query": "Optimierung der GC-Schwellenwerte (gc.set_threshold) für latenzsensitive Echtzeit-Systeme zur Vermeidung von GC-Pausen."
    })
    problems.append({
        "id": "72", "topic": "Netzwerkprogrammierung (Epoll vs Select)",
        "query": "Vergleich von I/O-Multiplexing-Verfahren und Implementierung eines performanten TCP-Servers mit dem 'selectors' Modul."
    })
    problems.append({
        "id": "73", "topic": "Numba JIT-Kompilierung",
        "query": "Einsatz von Numba (@jit(nopython=True)) zur Echtzeit-Vektorisierung mathematischer Berechnungen auf NumPy-Arrays."
    })
    problems.append({
        "id": "74", "topic": "Design Pattern: Ringpuffer-Producer",
        "query": "Implementierung des Producer-Consumer Patterns mittels Threading und queue.Queue unter Berücksichtigung von Backpressure."
    })
    problems.append({
        "id": "75", "topic": "Ctypes / C-DLL Einbindung",
        "query": "Einbindung einer kompilierten C-Bibliothek (.dll/.so) in Python mittels ctypes zur Ansteuerung einer mechatronischen USB-Messkarte."
    })
    problems.append({
        "id": "76", "topic": "Weak-References (weakref)",
        "query": "Verwendung von weakref-Modulen zur Speicherung großer Sensor-Caches ohne Beeinträchtigung des Garbage Collectors."
    })
    problems.append({
        "id": "77", "topic": "FastAPI Web-Sockets",
        "query": "Entwurf eines echtzeitfähigen WebSocket-Endpoints in FastAPI zur Übertragung hochfrequenter Telemetriedaten an ein UI."
    })
    problems.append({
        "id": "78", "topic": "Pytest Testabdeckung (Mocking)",
        "query": "Erstellung einer robusten Pytest-Suite unter Verwendung von pytest-mock zur Simulation fehlerhafter Hardware-Schnittstellen."
    })
    problems.append({
        "id": "79", "topic": "Python Startup-Optimierung",
        "query": "Analyse und Reduzierung der Startup-Zeit eines CLI-Agenten durch Lazy Imports und Vorkompilierung von Modulen."
    })
    problems.append({
        "id": "80", "topic": "Daten-Serialisierung (Protobuf vs JSON)",
        "query": "Benchmark und Implementierung von Google Protocol Buffers (Protobuf) als Ersatz für JSON bei hochfrequenten Netzwerk-Paketen."
    })

    # 5. App-Architektur & Streamlit (81-90)
    problems.append({
        "id": "81", "topic": "Custom Streamlit Components",
        "query": "Entwicklung einer maßgeschneiderten HTML/JS Streamlit-Komponente zur interaktiven Darstellung eines mechatronischen 3D-Roboterarms (Three.js)."
    })
    problems.append({
        "id": "82", "topic": "Streamlit State-Management",
        "query": "Best Practices zur Sitzungsverwaltung (st.session_state) in komplexen, mehrseitigen Streamlit-Dashboards zur Vermeidung von Rerender-Verlusten."
    })
    problems.append({
        "id": "83", "topic": "React/Vite Hot-Reloading",
        "query": "Optimale Konfiguration von Vite und HMR (Hot Module Replacement) für ein React-Frontend im Zusammenspiel mit einer Python-Backend-API."
    })
    problems.append({
        "id": "84", "topic": "Realtime Charting (ECharts/Plotly)",
        "query": "Echtzeit-Aktualisierung von dynamischen Diagrammen in einer Web-App zur flüssigen Darstellung von Telemetriedaten ohne Page-Reload."
    })
    problems.append({
        "id": "85", "topic": "Streamlit Performance Caching",
        "query": "Einsatz von st.cache_data und st.cache_resource zur performanten Pufferung großer historischer Finanz-Datenbanksätze."
    })
    problems.append({
        "id": "86", "topic": "Web-App Security (JWT Auth)",
        "query": "Implementierung eines robusten JWT (JSON Web Token) Authentifizierungs- und Autorisierungs-Systems für eine Steuerungs-API."
    })
    problems.append({
        "id": "87", "topic": "Streamlit Docker-Deployment",
        "query": "Erstellung eines optimierten Dockerfiles für eine Streamlit-Anwendung zur Minimierung der Image-Größe und schnellen Cloud-Bereitstellung."
    })
    problems.append({
        "id": "88", "topic": "Responsive Grid Layouts",
        "query": "Entwurf eines CSS-Flexbox und CSS-Grid basierten Dashboards zur nahtlosen Anpassung an Desktop-, Tablet- und Mobil-Bildschirme."
    })
    problems.append({
        "id": "89", "topic": "Server-Sent Events (SSE)",
        "query": "Implementierung von Server-Sent Events (SSE) als leichtgewichtige Alternative zu WebSockets zur unidirektionalen Live-Statusübertragung."
    })
    problems.append({
        "id": "90", "topic": "Micro-Frontend Architektur",
        "query": "Konzepte zur modularen Skalierung von Webanwendungen mittels Module Federation zur teamunabhängigen Entwicklung."
    })

    # 6. Astrologische Kybernetik (91-100)
    problems.append({
        "id": "91", "topic": "Merkur-Transit Berechnung",
        "query": "Berechnung der geozentrischen Ekliptik-Länge von Merkur zur Identifikation von retrograden Phasen mittels astronomischer Ephemeriden."
    })
    problems.append({
        "id": "92", "topic": "Mondphasen-Marktkorrelation",
        "query": "Statistische Analyse zur Überprüfung von Korrelationen zwischen Mondphasen (Vollmond vs. Neumond) und der Volatilität im S&P 500."
    })
    problems.append({
        "id": "93", "topic": "Astrologischer Task-Scheduler",
        "query": "Entwurf eines Task-Schedulers, der rechenintensive Hintergrundprozesse auf astronomische Konstellationen (z.B. Mars-Aspekte) abstimmt."
    })
    problems.append({
        "id": "94", "topic": "Jupiter-Saturn Konjunktionszyklus",
        "query": "Historische Analyse und systemtheoretische Modellbildung der makroökonomischen Wellen anhand des 20-jährigen Jupiter-Saturn Zyklus."
    })
    problems.append({
        "id": "95", "topic": "Ekliptik-Koordinatentransformation",
        "query": "Mathematische Umrechnung von äquatorialen Koordinaten (Rektaszension/Deklination) in ekliptikale Koordinaten für planetare Berechnungen."
    })
    problems.append({
        "id": "96", "topic": "Mercury Retrograde API Guard",
        "query": "Implementierung eines Software-Sicherheitsfilters, der während Merkur-Retrograden Phasen erweiterte Code-Validierungen vor Commits erzwingt."
    })
    problems.append({
        "id": "97", "topic": "Sonne-Erruptionen & Netzwerklatenz",
        "query": "Modell zur Schätzung von potenziellen Netzwerkpaketverlusten und Latenzschwankungen in HFT-Infrastrukturen durch solare Aktivitätszyklen."
    })
    problems.append({
        "id": "98", "topic": "Planeten-Aspekte (Winkelberechnung)",
        "query": "Algorithmus zur präzisen Berechnung von Winkelabständen (Aspekten wie Konjunktion, Opposition, Quadrat) zwischen zwei Planeten."
    })
    problems.append({
        "id": "99", "topic": "Chrono-Cybernetic Task Allocation",
        "query": "Entwurf eines mechatronischen Steuerungskonzepts, das Entscheidungsintervalle basierend auf biologischen und planetaren Zyklen anpasst."
    })
    problems.append({
        "id": "100", "topic": "Pluto-Transit & Systemumbruch",
        "query": "Systemtheoretische Interpretation des Begriffs 'Kreative Zerstörung' (Schumpeter) parallelisiert mit planetaren Transits von äußeren Planeten."
    })

    with open("problems.json", "w", encoding="utf-8") as f:
        json.dump(problems, f, indent=4, ensure_ascii=False)

    print(f"[OK] 100 hochpräzise mechatronisch-finanztechnische Aufgaben in 'problems.json' generiert!")
    return problems

if __name__ == "__main__":
    generate()
