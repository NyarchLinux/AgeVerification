pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'ageverification'
gnome = import('gnome')

gnome.compile_resources('ageverification',
  'ageverification.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'ageverification.in',
  output: 'ageverification',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

ageverification_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'questions.py',
  'assets.py',
]

install_data(ageverification_sources, install_dir: moduledir)

# Media assets (logos, optional subway video, question/option/transition images).
# install_subdir keeps the source dir name, so this lands at <moduledir>/assets/
# which is exactly where assets.py looks. Replacing files in-place under
# src/assets/ is enough — no rebuild of code.
install_subdir('assets', install_dir: moduledir)
