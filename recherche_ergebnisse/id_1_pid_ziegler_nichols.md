# ID 1: PID-Regler Ziegler-Nichols

## Problembeschreibung
Die Ziegler-Nichols-Methode ist ein heuristisches Verfahren zur Bestimmung der Parameter eines PID-Reglers ($K_p$, $T_i$, $T_d$).

## Mathematische Grundlagen
Die allgemeine Übertragungsfunktion eines PID-Reglers im Zeitbereich lautet:
$$ u(t) = K_p \left( e(t) + \frac{1}{T_i} \int_{0}^{t} e(\tau) d\tau + T_d \frac{de(t)}{dt} \right) $$

Dabei ist:
- $u(t)$: Stellgröße
- $e(t)$: Regeldifferenz (Sollwert - Istwert)
- $K_p$: Proportionalbeiwert
- $T_i$: Nachstellzeit
- $T_d$: Vorhaltzeit

## Methode der Stabilitätsgrenze (Schwingversuch)
Das geschlossene Regelsystem wird an die Stabilitätsgrenze gebracht:
1. $T_i \to \infty$ (I-Anteil deaktiviert) und $T_d = 0$ (D-Anteil deaktiviert).
2. Der Proportionalbeiwert $K_p$ wird langsam erhöht, bis die Regelgröße eine ungedämpfte, harmonische Dauerschwingung ausführt. Dieser Wert wird als kritischer Verstärkungsfaktor $K_{u}$ (oder $K_{krit}$) bezeichnet.
3. Die Periodendauer dieser Schwingung wird als kritische Periodendauer $T_{u}$ (oder $T_{krit}$) gemessen.

## Parametrierung
Nach Ziegler-Nichols ergeben sich die Parameter für die verschiedenen Reglertypen wie folgt:

| Reglertyp | $K_p$ | $T_i$ | $T_d$ |
|-----------|-------|-------|-------|
| **P** | $0.5 \cdot K_u$ | $\infty$ | $0$ |
| **PI** | $0.45 \cdot K_u$ | $0.83 \cdot T_u$ | $0$ |
| **PID** | $0.6 \cdot K_u$ | $0.5 \cdot T_u$ | $0.125 \cdot T_u$ |

Diese Parameter bieten einen robusten Startpunkt, führen jedoch oft zu einem leichten Überschwingen von ca. 25%, was je nach mechatronischem System nachträglich feinjustiert werden muss.
