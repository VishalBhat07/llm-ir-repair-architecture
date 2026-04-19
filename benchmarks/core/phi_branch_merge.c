int phi_branch_merge(int flag, int a, int b) {
    int x;
    if (flag) {
        x = a + b;
    } else {
        x = a - b;
    }
    return x * 2;
}
