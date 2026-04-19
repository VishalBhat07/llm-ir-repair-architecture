static int helper_add_one(int a, int b) {
    return a + b + 1;
}

static int helper_times_two(int x) {
    return x * 2;
}

int function_chain_calls_variant(int a, int b) {
    return helper_times_two(helper_add_one(a, b));
}
