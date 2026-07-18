#include <assert.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *read_file(const char *path)
{
    FILE *file = fopen(path, "rb");
    assert(file != 0);
    assert(fseek(file, 0L, SEEK_END) == 0);
    long size = ftell(file);
    assert(size >= 0);
    assert(fseek(file, 0L, SEEK_SET) == 0);

    char *buffer = malloc((size_t)size + 1u);
    assert(buffer != 0);
    size_t n = fread(buffer, 1u, (size_t)size, file);
    fclose(file);
    assert(n == (size_t)size);
    buffer[n] = '\0';
    return buffer;
}

static int manifest_count(const char *manifest)
{
    const char *field = strstr(manifest, "\"count\": ");
    assert(field != 0);
    return atoi(field + strlen("\"count\": "));
}

static int count_generated_declarations(void)
{
    DIR *dir = opendir("declarations/omnicron-port");
    assert(dir != 0);

    int count = 0;
    struct dirent *entry;
    while ((entry = readdir(dir)) != 0) {
        const char *name = entry->d_name;
        size_t len = strlen(name);
        if (len > 8u && strcmp(name + len - 8u, ".omilisp") == 0) {
            count++;
        }
    }

    closedir(dir);
    return count;
}

static void assert_contains(const char *text, const char *needle)
{
    assert(strstr(text, needle) != 0);
}

static void test_manifest_counts(void)
{
    printf("Testing Omnicron bulk port manifest counts\n");

    char *manifest = read_file("declarations/omnicron-port/MANIFEST.json");
    int declared = manifest_count(manifest);
    int files = count_generated_declarations();

    assert(declared >= 400);
    assert(files == declared);
    assert_contains(manifest, "\".c\": 24");
    assert_contains(manifest, "\".mjs\": 73");
    assert_contains(manifest, "\".md\": 115");
    assert_contains(manifest, "\".pdf\": 27");
    assert_contains(manifest, "\"code\": 130");
    assert_contains(manifest, "\"declaration\": 113");
    assert_contains(manifest, "\"document\": 120");
    assert_contains(manifest, "\"carrier\": 57");

    free(manifest);
    printf("  OK manifest matches generated declaration set\n\n");
}

static void test_representative_declarations(void)
{
    printf("Testing representative Omnicron converted declarations\n");

    char *c_decl = read_file("declarations/omnicron-port/logic-interp-c.omilisp");
    assert_contains(c_decl, "(family code)");
    assert_contains(c_decl, "(function-count 35)");
    assert_contains(c_decl, "(source-content-copied false)");
    assert_contains(c_decl, "(sp-boundary required-before-dot)");
    free(c_decl);

    char *json_decl = read_file("declarations/omnicron-port/polyform-attributes-rules-aztec-json.omilisp");
    assert_contains(json_decl, "(family declaration)");
    assert_contains(json_decl, "(json-valid true)");
    assert_contains(json_decl, "(json-kind \"object\")");
    free(json_decl);

    char *pdf_decl = read_file("declarations/omnicron-port/dev-docs-front-end-hardware-riscv-spec-20191213-pdf.omilisp");
    assert_contains(pdf_decl, "(family carrier)");
    assert_contains(pdf_decl, "(text-readable false)");
    assert_contains(pdf_decl, "(carrier-authority false)");
    free(pdf_decl);

    printf("  OK representative declarations preserve type and authority metadata\n\n");
}

int main(void)
{
    printf("Testing Omnicron Bulk OMI-Lisp Port\n");
    printf("===================================\n\n");

    test_manifest_counts();
    test_representative_declarations();

    printf("===================================\n");
    printf("ALL OMNICRON BULK PORT TESTS PASSED\n");
    return 0;
}
