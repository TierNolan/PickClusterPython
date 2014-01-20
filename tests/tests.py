_failed = 0
_passed = 0
_skipped = 0


def run_test(test_module_name):
    print
    test_module = __import__(test_module_name, globals(), locals(), [], -1)
    print test_module.get_name()
    tests = test_module.get_tests()
    for test_info in tests:
        test_name = test_info[0]
        test = test_info[1]
        if len(test_info) > 2 and not test_info[2]:
            skip = True
        else:
            skip = False

        if skip:
            result = "SKIPPED"
            global _skipped
            _skipped += 1
        else:
            try:
                test()
                result = "PASSED"
                global _passed
                _passed += 1
            except AssertionError as ae:
                result = 'FAILED (' + ae.message + ')'
                global _failed
                _failed += 1
        print "  " + test_name + ": " + result

run_test('difficulty_target_test')
run_test('byte_array_codec_test')

print
print "Test Results"
print "Passed %d" % _passed
print "Failed %d" % _failed
print "Skipped %d" % _skipped
print
if _failed > 0:
    print "<<<<< TEST FAILURES >>>>"
else:
    print "<<<<< TESTS PASSED >>>>>"