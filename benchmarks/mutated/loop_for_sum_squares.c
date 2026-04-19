int loop_for_sum_squares(int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += i * i;
    }
    return total;
}
