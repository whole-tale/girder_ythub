add_python_test(basic PLUGIN wholetale)
add_python_test(harvester PLUGIN wholetale)
add_python_test(recipe PLUGIN wholetale)
add_python_test(image PLUGIN wholetale)
add_python_test(tale PLUGIN wholetale)
add_python_test(instance PLUGIN wholetale)
add_python_test(constants PLUGIN wholetale)
add_python_test(utils PLUGIN wholetale)
add_python_test(dataone_register
  PLUGIN wholetale
  EXTERNAL_DATA
  plugins/wholetale/test_find_resource_pid.txt
  plugins/wholetale/test_get_package_list_flat.txt
  plugins/wholetale/test_get_package_list_nested.txt
)
add_python_style_test(python_static_analysis_wholetale
                      "${PROJECT_SOURCE_DIR}/plugins/wholetale/server")
