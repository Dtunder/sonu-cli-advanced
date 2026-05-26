def calculate_cybernetic_stability(population, resources):
    # This will crash if resources is 0
    if resources == 0:
        return 0  # Keine Stabilitaet, wenn keine Ressourcen vorhanden sind
    stability = population / resources
    return stability

if __name__ == "__main__":
    print("Starte Oekolopoly Simulation...")
    pop = 1000
    res = 0
    
    result = calculate_cybernetic_stability(pop, res)
    print(f"Ergebnis: {result}")
