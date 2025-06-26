import random

def generate_six_digit_random_number():
    return random.randint(100000, 999999)

if __name__ == "__main__":
    print(generate_six_digit_random_number())
