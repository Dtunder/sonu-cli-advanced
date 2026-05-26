# Problem ID 21: L3-Orderbook Aggregation

## C++ Code-Ansatz für eine lock-freie Struktur

In High-Frequency Trading (HFT) Systemen ist die Latenz bei der Verarbeitung von Orderbook-Updates kritisch. Eine L3-Orderbook-Aggregation (welche einzelne Orders statt nur Preis-Level speichert) erfordert extrem schnelle Insert-, Modify- und Delete-Operationen. Ein Ansatz für eine lock-freie Datenstruktur in C++ nutzt Hazard Pointers oder Epoch-Based Reclamation zur Speicherverwaltung und atomare Operationen auf einer kombinierten Struktur wie einer Skip-List oder einer Array-basierten, vorkonsumierten Speicher-Arena.

Im Folgenden skizzieren wir einen Ansatz, der eine intrusive, lock-freie verlinkte Liste je Preis-Level (`PriceLevel`) innerhalb eines lock-freien Arrays oder einer Skip-List für die Level-Verwaltung kombiniert.

### C++ Konzept und Architektur

1. **Speicher-Arena (Memory Pool):**
   Vermeidung von dynamischer Speicherallokation (`new`/`delete`) im kritischen Pfad. Vorallokierte Arrays für `Order`-Knoten. Lock-freie Indizes (z.B. mittels `std::atomic<uint32_t>`) dienen als Pointer in die Arena.

2. **Lock-freie Order-Liste pro Preis-Level:**
   Nutzt den Compare-And-Swap (CAS) Algorithmus von Harris für verlinkte Listen, um Orders sicher einzufügen und zu löschen (z.B. mittels *logical deletion* und späterem *physical unlink*).

```cpp
#include <atomic>
#include <cstdint>
#include <memory>

// Forward declarations
struct OrderNode;

// Pointer Type Definition utilizing lower bits for marking (Logical Deletion)
// In a 64-bit architecture, pointers are aligned, leaving lower bits free.
// For array-based arena allocation, indices can be used and MSB for mark bit.
struct MarkedPointer {
    uint32_t index_and_mark;

    // Extract Index
    uint32_t get_index() const { return index_and_mark & ~1; }
    // Extract Mark
    bool is_marked() const { return (index_and_mark & 1) != 0; }

    static uint32_t make(uint32_t index, bool mark) {
        return (index & ~1) | (mark ? 1 : 0);
    }
};

struct Order {
    uint64_t order_id;
    uint32_t size;
    uint64_t price;
    bool is_bid;
};

// Intrusive Node within a pre-allocated Memory Arena
struct OrderNode {
    Order order;
    std::atomic<uint32_t> next; // MarkedPointer index
};

class LockFreePriceLevel {
private:
    std::atomic<uint32_t> head;
    // Note: A MemoryPool reference is required here to translate indices to OrderNode*
    // MemoryPool& pool;

public:
    LockFreePriceLevel() {
        head.store(0); // Assuming 0 is Null/Sentinel
    }

    // Insert an order at the end or based on time priority
    // Simplified insertion logic at the head for O(1)
    void insert(uint32_t new_node_index, OrderNode* new_node, class MemoryPool& pool) {
        uint32_t current_head = head.load(std::memory_order_relaxed);
        do {
            new_node->next.store(current_head, std::memory_order_relaxed);
            // CAS operation
        } while (!head.compare_exchange_weak(
                    current_head,
                    new_node_index,
                    std::memory_order_release,
                    std::memory_order_relaxed));
    }

    // Cancel (Delete) an order
    // Uses Harris' mark-bit technique
    bool cancel(uint64_t order_id, class MemoryPool& pool) {
        // Implementation requires finding the node, marking its 'next' pointer
        // to logically delete it, and subsequently CAS-ing the predecessor's
        // 'next' to physically unlink it.
        // Due to complexity, this involves a 'find' subroutine that cleans up
        // marked nodes as it traverses.
        return true;
    }
};

class L3OrderBook {
private:
    // For Price levels, a lock-free Skip-List or a dense array map (if price range is bounded/normalized)
    // is often used.
    // std::array<LockFreePriceLevel, MAX_PRICE_TICKS> price_levels;

    // Memory arena for node allocation avoiding syscalls
    // MemoryPool pool;

public:
    void add_order(const Order& order) {
        // 1. Allocate node from pool (lock-free pop from free-list)
        // 2. Map order.price to a PriceLevel
        // 3. Insert into LockFreePriceLevel
    }

    void cancel_order(uint64_t order_id, uint64_t price) {
        // 1. Map price to PriceLevel
        // 2. Cancel order in LockFreePriceLevel
        // 3. Return node to MemoryPool
    }
};
```

### Zusammenfassung der kritischen HFT-Konzepte:
- **Lock-Free Memory Management**: Kein `std::mutex`, kein `new`/`delete` zur Laufzeit. Alles läuft über atomares CAS (`compare_exchange_weak`/`strong`) und vorkonsumierten Speicher (Memory Arenas).
- **ABA Problem**: Da wir Indizes in einer Memory-Arena recyclen, muss das ABA-Problem mitigiert werden. Dies geschieht entweder durch Hazard Pointers, Epoch-Based Reclamation (z.B. RCU) oder durch Erweitern des Pointers/Index um einen ABA-Counter (z.B. in einem 64-bit struct `struct { uint32_t index; uint32_t aba_counter; }`).
- **Data Locality**: Um Cache-Misses zu minimieren, werden Nodes häufig blockweise in Cache-Line-Größe (64 Bytes) alloziert und traversiert.

Dieser Ansatz reduziert den Tail-Latency Jitter dramatisch, da Threads niemals durch OS-Scheduler-Locks blockiert werden.
