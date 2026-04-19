int sign_flip_when_negative(int a) {
    int x = a;
    if (x < 0) {
        x = 0 - x;
    }
    return x + 2;
}
