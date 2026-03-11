calculate_weighted_mean <- function(pi_matrix) {
  weights <- as.numeric(gsub("%", "", rownames(pi_matrix)))
  
  if (length(weights) != nrow(pi_matrix)) {
    stop("Liczba wierszy macierzy nie zgadza się z liczbą wag (procentów).")
  }
  
  weighted_means <- apply(pi_matrix, 2, function(x) {
    sum(weights * x) / sum(x)
  })
  
  result <- data.frame(column = colnames(pi_matrix),
                       weighted_mean = weighted_means,
                       row.names = NULL)
  
  return(result)
}
