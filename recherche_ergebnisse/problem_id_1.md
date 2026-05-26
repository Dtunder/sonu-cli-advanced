# Problem ID 1: PID-Regler Ziegler-Nichols

## Mathematisch-Präzise Lösung

Die Ziegler-Nichols-Methode (Z-N) ist ein heuristisches Verfahren zur Bestimmung der Parameter eines PID-Reglers. Es existieren primär zwei Varianten: Die Sprungantwort-Methode (Open-Loop) und die Stabilitätsrand-Methode (Closed-Loop).

### 1. Stabilitätsrand-Methode (Closed-Loop)
Diese Methode basiert auf der Bestimmung der kritischen Verstärkung $K_{krit}$ und der kritischen Schwingungsdauer $T_{krit}$, bei der das geschlossene System (nur mit P-Regler) eine ungedämpfte Dauerschwingung ausführt.

Die Übertragungsfunktion des idealen PID-Reglers im Zeitbereich lautet:
$$ u(t) = K_p \left( e(t) + \frac{1}{T_i} \int_{0}^{t} e(\tau) d\tau + T_d \frac{de(t)}{dt} \right) $$

Dabei ist:
- $K_p$: Proportionalbeiwert
- $T_i$: Nachstellzeit (Integralzeit)
- $T_d$: Vorhaltzeit (Differentialzeit)
- $e(t)$: Regeldifferenz ($w(t) - y(t)$)

Nach Ziegler-Nichols ergeben sich die Parameter für den Regler wie folgt:

| Reglertyp | $K_p$ | $T_i$ | $T_d$ |
|-----------|-------|-------|-------|
| **P** | $0.5 \cdot K_{krit}$ | $\infty$ | $0$ |
| **PI** | $0.45 \cdot K_{krit}$ | $0.85 \cdot T_{krit}$ | $0$ |
| **PID** | $0.6 \cdot K_{krit}$ | $0.5 \cdot T_{krit}$ | $0.125 \cdot T_{krit}$ |

### 2. Sprungantwort-Methode (Open-Loop)
Hierbei wird die Sprungantwort der offenen Regelstrecke auf einen Einheitssprung analysiert. Es werden die Verzugszeit $T_u$ und die Ausgleichszeit $T_g$ (oder die maximale Steigung $K_s = \frac{K}{T_g}$) ermittelt, wobei $K$ die Streckenverstärkung ist.

Die Parameter nach Ziegler-Nichols lauten in diesem Fall:

| Reglertyp | $K_p$ | $T_i$ | $T_d$ |
|-----------|-------|-------|-------|
| **P** | $\frac{T_g}{K \cdot T_u}$ | $\infty$ | $0$ |
| **PI** | $0.9 \cdot \frac{T_g}{K \cdot T_u}$ | $3.3 \cdot T_u$ | $0$ |
| **PID** | $1.2 \cdot \frac{T_g}{K \cdot T_u}$ | $2.0 \cdot T_u$ | $0.5 \cdot T_u$ |

### Mathematische Herleitung und Stabilität
Die empirischen Formeln wurden von J.G. Ziegler und N.B. Nichols (1942) so gewählt, dass die Sprungantwort des geschlossenen Regelkreises eine Amplitudendämpfung von etwa $1/4$ pro Periode (Quarter Decay Ratio) aufweist:
$$ \frac{x_{k+1}}{x_k} \approx 0.25 $$
wobei $x_k$ die Amplitude der $k$-ten Schwingung des Fehlersignals ist.
Diese Heuristik stellt einen aggressiven Kompromiss zwischen schneller Ausregelung und Stabilitätsreserve dar. In modernen mechatronischen Systemen dient die Z-N-Methode oft als robuster Startpunkt für weiterführende analytische Optimierungen (z.B. Polvorgabe oder frequenzgangbasierte Synthese).
