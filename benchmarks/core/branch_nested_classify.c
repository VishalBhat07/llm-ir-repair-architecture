int branch_nested_classify(int a, int b) {
    if (a > 0) {
        if (b > 0) {
            return 3;
        }
        return 2;
    }
    if (b > 0) {
        return 1;
    }
    return 0;
}
