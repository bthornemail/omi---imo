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
    DIR *dir = opendir("declarations/mcrsgsp-port");
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
    printf("Testing MCRSGSP bulk port manifest counts\n");

    char *manifest = read_file("declarations/mcrsgsp-port/MANIFEST.json");
    int declared = manifest_count(manifest);
    int files = count_generated_declarations();

    assert(declared == 56);
    assert(files == declared);
    assert_contains(manifest, "\".js\": 22");
    assert_contains(manifest, "\".mjs\": 10");
    assert_contains(manifest, "\".janet\": 3");
    assert_contains(manifest, "\"code\": 32");
    assert_contains(manifest, "\"declaration\": 9");
    assert_contains(manifest, "\"document\": 3");
    assert_contains(manifest, "\"carrier\": 1");

    free(manifest);
    printf("  OK manifest matches generated declaration set\n\n");
}

static void test_representative_declarations(void)
{
    printf("Testing representative MCRSGSP converted declarations\n");

    char *resolver_decl = read_file("declarations/mcrsgsp-port/tools-omi-resolve-resolve-mjs.omilisp");
    assert_contains(resolver_decl, "(sid mcrsgsp-port.tools-omi-resolve-resolve-mjs)");
    assert_contains(resolver_decl, "(kind mcrsgsp.source-candidate)");
    assert_contains(resolver_decl, "(gs mcrsgsp)");
    assert_contains(resolver_decl, "(family code)");
    assert_contains(resolver_decl, "(function-count 16)");
    assert_contains(resolver_decl, "(source-content-copied false)");
    free(resolver_decl);

    char *package_decl = read_file("declarations/mcrsgsp-port/package-json.omilisp");
    assert_contains(package_decl, "(family declaration)");
    assert_contains(package_decl, "(json-valid true)");
    assert_contains(package_decl, "(json-key-count 9)");
    free(package_decl);

    char *carrier_decl = read_file("declarations/mcrsgsp-port/golden-hello-k3n5-reconstructed-bin.omilisp");
    assert_contains(carrier_decl, "(family carrier)");
    assert_contains(carrier_decl, "(text-readable false)");
    assert_contains(carrier_decl, "(carrier-authority false)");
    free(carrier_decl);

    printf("  OK representative declarations preserve source metadata and authority boundary\n\n");
}

int main(void)
{
    printf("Testing MCRSGSP Bulk OMI-Lisp Port\n");
    printf("==================================\n\n");

    test_manifest_counts();
    test_representative_declarations();

    printf("==================================\n");
    printf("ALL MCRSGSP BULK OMI-LISP PORT TESTS PASSED\n");
    return 0;
}
