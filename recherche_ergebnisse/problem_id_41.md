# Problem ID 41: PPO in kontinuierlichen Action Spaces

## Kritische Hyperparameter für Stabilität

Proximal Policy Optimization (PPO) ist ein hochmodernes Reinforcement Learning (RL) Algorithmus-Framework, das darauf abzielt, die Stabilität und Robustheit von Policy-Gradient-Methoden zu verbessern. Insbesondere bei kontinuierlichen Action Spaces (z.B. Robotik, Drohnensteuerung, HFT-Parameter-Tuning) ist die Wahl der Hyperparameter entscheidend, um katastrophale Policy-Updates zu vermeiden (Catastrophic Forgetting) und Konvergenz sicherzustellen.

PPO optimiert ein "surrogate objective", welches die Update-Größe beschneidet (Clipping). Die Stabilität in kontinuierlichen Räumen hängt maßgeblich von den folgenden kritischen Hyperparametern ab:

### 1. Clipping-Parameter ($\epsilon$)
- **Funktion**: Beschränkt das Verhältnis zwischen der neuen und der alten Policy ($r_t(\theta) = \frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{old}}(a_t|s_t)}$). Das Objective wird auf das Intervall $[1-\epsilon, 1+\epsilon]$ geclippt.
- **Kritikalität**: Ein zu großes $\epsilon$ führt zu zu großen Updates, was die Stabilität zerstört (ähnlich zu Vanilla Policy Gradient). Ein zu kleines $\epsilon$ verlangsamt den Lernprozess enorm.
- **Typische Werte**: $0.1$ bis $0.3$ (häufig $0.2$). In hochdynamischen kontinuierlichen Räumen tendenziell eher in Richtung $0.1$ bis $0.15$ beginnen, um zu große Sprünge im Action Space zu vermeiden.

### 2. Learning Rate (Lernrate, $\alpha$) für den Actor und Critic
- **Funktion**: Bestimmt die Schrittweite bei der Optimierung (meist Adam Optimizer).
- **Kritikalität**: In kontinuierlichen Räumen sind die Gradienten oft verrauscht. Eine zu hohe Lernrate für den Actor (Policy Network) führt zu oszillierendem Verhalten und Policy Collapse (die Varianz der ausgegebenen Gauss-Verteilung kollabiert zu 0).
- **Typische Werte**: $10^{-4}$ bis $3 \cdot 10^{-4}$. Oft ist es vorteilhaft, die Lernrate linear über die Trainingsdauer (Annealing) zu reduzieren. Der Critic (Value Network) bekommt oft eine leicht höhere Lernrate (z.B. $10^{-3}$), da er nur eine Regression (Value-Estimation) durchführt und schneller konvergieren soll als die Policy.

### 3. Generalized Advantage Estimation (GAE) Parameter ($\lambda$) und Discount Factor ($\gamma$)
- **Funktion**: GAE glättet den Trade-off zwischen Bias und Varianz bei der Schätzung des Advantage $A_t$. $\gamma$ diskontiert zukünftige Belohnungen.
- **Kritikalität**: In kontinuierlichen Aufgaben (oft mit langen Episoden) ist die Varianz des Advantage-Schätzers riesig. Ein schlechter Advantage führt zu falschen Updates.
- **Typische Werte**:
  - $\lambda \approx 0.95$ bis $0.99$ (hilft stark bei der Varianzreduktion auf Kosten von etwas Bias).
  - $\gamma \approx 0.99$ bis $0.999$ (je nach Episodenlänge).

### 4. Entropy Coefficient ($c_2$)
- **Funktion**: Fügt der Loss-Funktion einen Bonus für Entropie hinzu, um Exploration zu fördern (verhindert premature convergence).
- **Kritikalität**: Bei kontinuierlichen Action Spaces wird die Policy meist durch eine Normalverteilung $\mathcal{N}(\mu, \sigma)$ parametrisiert. Wenn die Standardabweichung $\sigma$ zu schnell gegen 0 geht, exploriert der Agent nicht mehr. Ein gut gewählter Entropie-Koeffizient hält $\sigma$ künstlich groß genug, bis die Policy sicher konvergiert.
- **Typische Werte**: $0.0$ bis $0.01$. Sehr oft wird er in PPO für kontinuierliche Räume auf $0.0$ gesetzt, wenn man stattdessen die initiale Standardabweichung der Aktionsverteilung fest vorgibt (z.B. log_std $= 0$ also $\sigma = 1$) und diese trainierbar macht. Ist dies nicht der Fall, ist ein kleiner Wert wie $0.005$ kritisch.

### 5. Batch Size und Minibatch Size / Optimization Epochs ($K$)
- **Funktion**: Wie viele Schritte werden in der Umgebung gesammelt (Rollout / Batch Size) bevor das Netzwerk geupdated wird, und wie oft (Epochs $K$) wird über diese Daten mit Minibatches iteriert.
- **Kritikalität**: Da PPO on-policy ist, müssen die Rollouts repräsentativ sein. Bei kontinuierlichen Systemen sind längere Trajektorien oft nötig, um den vollen State-Space zu beleuchten. Zu viele Epochen über denselben Batch führen zum Overfitting auf alte Daten, was trotz Clipping das Trust Region Constraint verletzt.
- **Typische Werte**:
  - Rollout Steps: $2048$ bis $4096$ (pro Environment).
  - Minibatch Size: $64$ bis $256$.
  - Epochs ($K$): $3$ bis $10$. Mehr als 10 Epochs führt oft zu Überanpassung (Overfitting) an das aktuelle Rollout.

### 6. Value Function Coefficient ($c_1$)
- **Funktion**: Skaliert den Loss des Critic Networks im Gesamt-Loss (falls Actor und Critic sich Parameter teilen).
- **Kritikalität**: Wenn Actor und Critic getrennte Netzwerke sind, ist dieser Parameter weniger relevant. Teilen sie sich Feature-Layer, kann ein dominanter Value Loss die Repräsentationsfähigkeit des Actors zerstören.
- **Typische Werte**: Meist $0.5$.

### Zusammenfassung für Stabilität in kontinuierlichen Räumen
Die absolut kritischsten Parameter für den Erfolg von PPO in kontinuierlichen Räumen sind die **Lernrate (und das Learning Rate Annealing)**, um Overshooting zu verhindern, sowie ein striktes **Clipping ($\epsilon \approx 0.2$)**, um die Trust Region einzuhalten. Eine adäquate **Batch Size** stellt sicher, dass die Advantage-Schätzungen (unterstützt durch **GAE $\lambda \approx 0.95$**) eine geringe Varianz aufweisen. Zuletzt ist die Behandlung der Aktions-Varianz ($\sigma$) entscheidend, die entweder durch den **Entropy Coefficient** oder durch ein trainierbares $\sigma$ mit passender Initialisierung gemanagt werden muss.
