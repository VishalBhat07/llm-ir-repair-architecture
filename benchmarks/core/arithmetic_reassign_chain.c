int arithmetic_reassign_chain(int a) {
    int x = a;
    x = x + 3;
    x = x * 2;
    return x - 1;
}
