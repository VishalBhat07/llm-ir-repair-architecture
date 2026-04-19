int loop_while_countdown_even(int n) {
    int total = 0;
    while (n > 0) {
        if ((n % 2) == 0) {
            total += n;
        }
        n = n - 1;
    }
    return total;
}
