# ID 21: L3-Orderbook Aggregation

## Problembeschreibung
Ein Level-3 (L3) Orderbook enthält einzelne Orders anstatt aggregierter Preisniveaus. Für den High-Frequency Trading (HFT) Kontext muss die Aggregation in Level-2 (L2) Daten (Preis-Level und aggregiertes Volumen) extrem performant und mit geringer Latenz erfolgen. Eine lock-freie (lock-free) Datenstruktur in C++ minimiert Thread-Contention.

## Ansatz: Lock-freie Struktur in C++

Für ein HFT-Szenario bietet sich eine Kombination aus `std::atomic` Arrays oder Wait-Free Queues an. Im Falle von Preisniveaus, bei denen der Wertebereich beschränkt oder vordefiniert sein kann (z.B. Ticks), lässt sich ein Array-basierter Ansatz nutzen.

### Skizze für eine lock-freie L2 Aggregation aus L3 Orders

Wir nutzen einen Ansatz, bei dem jedes Preisniveau atomar aktualisiert wird.

```cpp
#include <atomic>
#include <vector>
#include <cstdint>

// Repräsentiert ein Preisniveau im Orderbuch
struct PriceLevel {
    std::atomic<uint64_t> volume{0};
    std::atomic<uint32_t> order_count{0};

    // Lock-freies Hinzufügen einer Order
    void add_order(uint64_t size) {
        volume.fetch_add(size, std::memory_order_relaxed);
        order_count.fetch_add(1, std::memory_order_relaxed);
    }

    // Lock-freies Entfernen einer Order
    void remove_order(uint64_t size) {
        volume.fetch_sub(size, std::memory_order_relaxed);
        order_count.fetch_sub(1, std::memory_order_relaxed);
    }

    // Lock-freies Auslesen des aggregierten Volumens
    uint64_t get_volume() const {
        return volume.load(std::memory_order_relaxed);
    }
};

// Vordefiniertes Array von Preisniveaus für O(1) Zugriff
// Der Index entspricht dem Preis (z.B. Preis in Ticks)
class L2Aggregator {
private:
    std::vector<PriceLevel> levels;

public:
    L2Aggregator(size_t max_ticks) : levels(max_ticks) {}

    // L3 Update: Neue Order
    void on_order_add(uint32_t price_tick, uint64_t size) {
        if (price_tick < levels.size()) {
            levels[price_tick].add_order(size);
        }
    }

    // L3 Update: Order storniert/ausgeführt
    void on_order_remove(uint32_t price_tick, uint64_t size) {
        if (price_tick < levels.size()) {
            levels[price_tick].remove_order(size);
        }
    }

    // Abfrage des L2-Volumens für einen bestimmten Preis
    uint64_t get_l2_volume(uint32_t price_tick) const {
        if (price_tick < levels.size()) {
            return levels[price_tick].get_volume();
        }
        return 0;
    }
};
```

### Eigenschaften der Lösung
- **Lock-Free:** Es werden keine Mutexe verwendet, stattdessen `std::atomic` mit `memory_order_relaxed`. Da beim bloßen Aggregieren keine strikte Ordering-Garantie zwischen unabhängigen Preisniveaus erforderlich ist, reicht `relaxed` für maximale Performance auf x86.
- **O(1) Zugriff:** Durch die Abbildung von Preisen auf Indizes (Ticks) erfolgen Updates und Abfragen in konstanter Zeit.
- **L3-Verknüpfung:** Das eigentliche L3-Orderbuch (Tracking individueller Order-IDs) wird separat gepflegt. Jedes Mal, wenn eine Order-ID hinzugefügt oder entfernt wird, erfolgt der entsprechende Aufruf in den `L2Aggregator`.
