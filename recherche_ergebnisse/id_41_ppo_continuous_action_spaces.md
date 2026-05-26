# ID 41: PPO in kontinuierlichen Action Spaces

## Problembeschreibung
Proximal Policy Optimization (PPO) ist ein state-of-the-art Reinforcement Learning Algorithmus, der in kontinuierlichen Action Spaces oft für Robotik (Mechatronik) und Finanz-Agents genutzt wird. Die Stabilität des Trainings in kontinuierlichen Räumen hängt stark von der korrekten Wahl der Hyperparameter ab, da die Policy typischerweise als Normalverteilung modelliert wird, deren Mittelwert und Varianz das neuronale Netz ausgibt.

## Kritische Hyperparameter für Stabilität

1. **Clipping Parameter ($\epsilon$)**
   - **Funktion:** Verhindert zu große Updates der Policy.
   - **Empfehlung:** Normalerweise zwischen 0.1 und 0.3. Ein Wert von 0.2 ist der Standard. Ein zu kleiner Wert verlangsamt das Lernen extrem, ein zu großer Wert führt zu Destabilisierung (Policy Collapse).

2. **Learning Rate (Lernrate)**
   - **Funktion:** Bestimmt die Schrittweite des Optimierers (meist Adam).
   - **Empfehlung:** Für kontinuierliche Räume oft etwas niedriger angesetzt (z.B. $3 \times 10^{-4}$ oder $1 \times 10^{-4}$). Ein *Learning Rate Schedule* (z.B. linear decay) ist essenziell, um gegen Ende des Trainings Stabilität zu gewährleisten.

3. **Entropy Coefficient (Entropie-Koeffizient)**
   - **Funktion:** Fördert Exploration, indem das Modell bestraft wird, wenn es sich zu sicher wird (Varianz der Normalverteilung geht gegen 0).
   - **Empfehlung:** In kontinuierlichen Räumen sehr sensibel. Meist zwischen 0.0 und 0.01. Ein zu hoher Wert verhindert Konvergenz, ein zu niedriger führt zu vorzeitiger Stagnation in lokalen Minima.

4. **Action Standard Deviation (Log-Std-Dev der Policy)**
   - **Funktion:** Initiales Explorationsrauschen. Wenn die Standardabweichung als trainierbarer Parameter (getrennt von den State-Features) modelliert wird, ist der Initialwert wichtig.
   - **Empfehlung:** Sollte groß genug sein, um den Action Space zu erkunden. Ein typischer Startwert liegt bei 0.0 (entspricht einer Standardabweichung von $e^0 = 1.0$), abhängig von der Normalisierung der Aktionen.

5. **Generalized Advantage Estimation (GAE) Parameter ($\lambda$) und Discount Factor ($\gamma$)**
   - **Funktion:** Steuern den Trade-off zwischen Bias und Varianz bei der Schätzung des Vorteils (Advantage).
   - **Empfehlung:** $\gamma \approx 0.99$ und $\lambda \approx 0.95$.

6. **Batch Size und Minibatch Size**
   - **Funktion:** Bestimmen, wie viele Daten für ein Gradienten-Update verwendet werden.
   - **Empfehlung:** In kontinuierlichen Spaces werden oft größere Batch-Sizes (z.B. 2048 oder 4096) benötigt, um rauscharme Gradienten zu erhalten. Minibatch-Sizes liegen oft bei 64 oder 128.

7. **Anzahl der Epochs pro Update (K-Epochs)**
   - **Funktion:** Wie oft das gesammelte Replay-Buffer aufgebraucht wird.
   - **Empfehlung:** Typischerweise 3 bis 10. Zu viele Epochs führen zu Overfitting auf den aktuellen Batch (destabilisiert PPO stark trotz Clipping).

## Zusammenfassung für Mechatronik / HFT
Besonders bei physischen Systemen (Mechatronik) oder verrauschten Umgebungen (HFT) ist die Balance zwischen *Clipping* (0.2) und *Learning Rate* ($\sim 10^{-4}$) sowie ein sorgfältiges Normalisieren von States und Actions (auf den Bereich $[-1, 1]$) das Fundament für ein stabiles PPO-Training in kontinuierlichen Aktionsräumen.
