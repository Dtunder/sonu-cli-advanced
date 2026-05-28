import numpy as np
import scipy.signal as signal
import matplotlib.pyplot as plt

# Parameter des PT3-Systems
T1 = 1.0
T2 = 2.0
T3 = 3.0
K_s = 1.0

# Übertragungsfunktion des PT3-Systems
numerator = [K_s]
denominator = [T1*T2*T3, T1*T2 + T2*T3 + T1*T3, T1 + T2 + T3, 1]
G = signal.TransferFunction(numerator, denominator)

# Simuliere die Sprungantwort
time = np.linspace(0, 20, 1000)
T, y = signal.step(G, T=time)

#Wendetangentenmethode
# Bestimmung des Wendepunkts   
max_slope_index = np.argmax(np.gradient(y))
max_slope_time = T[max_slope_index]
max_slope_value = y[max_slope_index]

# Steigung der Wendetangente
m = np.gradient(y)[max_slope_index]

# berechnung des Schnittpunkts der Wendetangente mit der Zeitachse (y=0)
T_u = -max_slope_value / m + max_slope_time

# berechnung des Schnittpunkts der Wendetangente mit dem Endwert
end_value = K_s
# Annäherung der Tangentengleichung und der Schnittpunkt mit der Endwertachse
T_a = (end_value - max_slope_value) / m + max_slope_time

# Berechnung der PID-Reglerparameter nach Ziegler-Nichols
Kp_1 = 1.2 * T_a / (T_u * K_s)
Tn_1 = 2 * T_u
Tv_1 = 0.5 * T_u

# Dauerschwingmethode
# Kritische Verstärkung
K_crit = (1/K_s) * (((T1*T2 + T2*T3 + T1*T3)*(T1+T2+T3) / (T1*T2*T3)) - 1)
# Kritische Kreisfrequenz
omega_crit = np.sqrt((T1+T2+T3) / (T1*T2*T3))
# Kritische Periodendauer
T_crit = 2 * np.pi / omega_crit

# PID-Reglerparameter nach Ziegler-Nichols Dauerschwingung
Kp_2 = 0.6 * K_crit
Tn_2 = 0.5 * T_crit
Tv_2 = 0.125 * T_crit

# Geschlossene Übertragungsfunktionen für beide Methoden
G_pid_1 = signal.TransferFunction([Kp_1, Kp_1/Tn_1, Tv_1*Kp_1], [1, 0.0])
G_closed_1 = signal.feedback(signal.convolve(G_pid_1.num, G.num), G_pid_1.den)
G_pid_2 = signal.TransferFunction([Kp_2, Kp_2/Tn_2, Tv_2*Kp_2], [1, 0.0])
G_closed_2 = signal.feedback(signal.convolve(G_pid_2.num, G.num), G_pid_2.den)

# Simulation der Sprungantwort des geschlossenen Regelkreises
T_closed_1, y_closed_1 = signal.step(G_closed_1, T=time)
T_closed_2, y_closed_2 = signal.step(G_closed_2, T=time)

# Visualisierung der Ergebnisse
plt.figure(figsize=(15, 12))
plt.subplot(2, 1, 1)
plt.plot(T, y, label='Sprungantwort G(s)')
plt.axvline(T_u, color='r', linestyle='--', label='T_u (Verzugszeit)')
plt.axvline(T_a, color='g', linestyle='--', label='T_a (Ausgleichszeit)')
plt.scatter([max_slope_time], [max_slope_value], color='b', label='Wendepunkt')
plt.title('Sprungantwort des PT3-Systems')
plt.xlabel('Zeit (s)')
plt.ylabel('Ausgangssignal')
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(T_closed_1, y_closed_1, label='Methode 1 (Wendetangente)')
plt.plot(T_closed_2, y_closed_2, label='Methode 2 (Dauerschwingung)')
plt.title('Vergleich der geschlossenen Regelkreise')
plt.xlabel('Zeit (s)')
plt.ylabel('Ausgangssignal')
plt.legend()

plt.tight_layout()
plt.savefig('ziegler_nichols_simulation.png')
plt.show()