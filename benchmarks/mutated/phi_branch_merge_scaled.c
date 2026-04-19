int phi_branch_merge_scaled(int flag, int a, int b) {
    int x;
    if (flag) {
        x = a * 2;
    } else {
        x = b * 3;
    }
    return x + 1;
}
