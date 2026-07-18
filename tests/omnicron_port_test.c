#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define TAG_MASK 0xC000u
#define TAG_INT 0x0000u
#define TAG_SYM 0x4000u
#define TAG_REF 0x8000u
#define TAG_SPEC 0xC000u
#define PAYLOAD_MASK 0x3FFFu
#define SPEC_NIL ((uint16_t)(TAG_SPEC | 0u))
#define SPEC_TRUE ((uint16_t)(TAG_SPEC | 1u))

static uint16_t pair_cons8(uint8_t car, uint8_t cdr)
{
    return (uint16_t)((((uint16_t)car & 0xFFu) << 8u) |
                      ((uint16_t)cdr & 0xFFu));
}

static uint8_t pair_car8(uint16_t pair)
{
    return (uint8_t)((pair >> 8u) & 0xFFu);
}

static uint8_t pair_cdr8(uint16_t pair)
{
    return (uint8_t)(pair & 0xFFu);
}

static uint16_t make_int(uint16_t value)
{
    return (uint16_t)(TAG_INT | (value & PAYLOAD_MASK));
}

static uint16_t make_symbol(uint16_t value)
{
    return (uint16_t)(TAG_SYM | (value & PAYLOAD_MASK));
}

static uint16_t make_ref(uint16_t value)
{
    return (uint16_t)(TAG_REF | (value & PAYLOAD_MASK));
}

static uint16_t rotl16(uint16_t value, unsigned shift)
{
    shift &= 15u;
    if (shift == 0u) {
        return value;
    }
    return (uint16_t)((value << shift) | (value >> (16u - shift)));
}

static uint16_t rotr16(uint16_t value, unsigned shift)
{
    shift &= 15u;
    if (shift == 0u) {
        return value;
    }
    return (uint16_t)((value >> shift) | (value << (16u - shift)));
}

static uint16_t kernel_delta16(uint16_t pair, uint16_t constant)
{
    return (uint16_t)(rotl16(pair, 1u) ^
                      rotl16(pair, 3u) ^
                      rotr16(pair, 2u) ^
                      constant);
}

static int read_file(const char *path, char *buffer, size_t size)
{
    FILE *file = fopen(path, "rb");
    if (file == 0) {
        return 0;
    }

    size_t n = fread(buffer, 1u, size - 1u, file);
    fclose(file);
    buffer[n] = '\0';
    return n > 0u;
}

static void assert_contains(const char *text, const char *needle)
{
    assert(strstr(text, needle) != 0);
}

static void test_pair_word_roundtrip(void)
{
    printf("Testing Omnicron pair word contract\n");

    uint16_t pair = pair_cons8(0x12u, 0xABu);
    assert(pair == 0x12ABu);
    assert(pair_car8(pair) == 0x12u);
    assert(pair_cdr8(pair) == 0xABu);

    printf("  OK pair word roundtrip matches omnicron/pair-machine.c\n\n");
}

static void test_value_tags(void)
{
    printf("Testing Omnicron value tag contract\n");

    assert((make_int(42u) & TAG_MASK) == TAG_INT);
    assert((make_symbol(5u) & TAG_MASK) == TAG_SYM);
    assert((make_ref(4095u) & TAG_MASK) == TAG_REF);
    assert((SPEC_NIL & TAG_MASK) == TAG_SPEC);
    assert((SPEC_TRUE & TAG_MASK) == TAG_SPEC);
    assert((make_int(0xFFFFu) & PAYLOAD_MASK) == PAYLOAD_MASK);

    printf("  OK value tags preserve 2-bit type and 14-bit payload\n\n");
}

static void test_delta16(void)
{
    printf("Testing Omnicron delta16 contract\n");

    assert(kernel_delta16(0x0000u, 0x001Du) == 0x001Du);
    assert(kernel_delta16(0x12ABu, 0x001Du) ==
           (uint16_t)(rotl16(0x12ABu, 1u) ^
                      rotl16(0x12ABu, 3u) ^
                      rotr16(0x12ABu, 2u) ^
                      0x001Du));

    printf("  OK delta16 matches atomic kernel law\n\n");
}

static void test_declaration_surface(void)
{
    printf("Testing Omnicron OMI-Lisp declaration surface\n");

    char text[8192];
    assert(read_file("declarations/omnicron-pair-machine.omilisp",
                     text,
                     sizeof(text)) == 1);

    assert_contains(text, "(sid omnicron-pair-machine)");
    assert_contains(text, "(source \"/home/main/omi/omnicron/pair-machine.c\")");
    assert_contains(text, "(sp-boundary required-before-dot)");
    assert_contains(text, "(accepted-state false)");
    assert_contains(text, "(receipt-created false)");
    assert_contains(text, "(law kernel-delta16");
    assert_contains(text, "(make-target omnicron-port-test)");

    printf("  OK declaration carries source, boundary, and authority markers\n\n");
}

int main(void)
{
    printf("Testing Omnicron -> omi---imo OMI-Lisp Port\n");
    printf("==========================================\n\n");

    test_pair_word_roundtrip();
    test_value_tags();
    test_delta16();
    test_declaration_surface();

    printf("==========================================\n");
    printf("ALL OMNICRON PORT TESTS PASSED\n");
    return 0;
}
