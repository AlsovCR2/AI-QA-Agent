// Paquete mínimo usado como proyecto de referencia de la evaluación.
package referencia

func ContarDisponibles(existencias []int) int {
	total := 0
	for _, n := range existencias {
		if n > 0 {
			total += n
		}
	}
	return total
}
