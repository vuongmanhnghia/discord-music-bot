{
  description = "Dev shell for Discord Music Bot";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;
        pyPkgs = pkgs.python312Packages;
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pyPkgs.pip
            pyPkgs.setuptools
            pyPkgs.wheel
            pkgs.pkg-config
            pkgs.libsodium
            pkgs.libopus
            pkgs.ffmpeg
          ];

          VENV_DIR = "./venv";

          shellHook = ''
            export PIP_DISABLE_PIP_VERSION_CHECK=1
            export PIP_NO_INPUT=1

            if [ ! -d "$VENV_DIR" ]; then
              echo "Creating virtualenv in $VENV_DIR..."
              ${python.interpreter} -m venv "$VENV_DIR"
            fi

            . "$VENV_DIR/bin/activate"

            python -m pip install -U pip setuptools wheel

            if [ -f requirements.txt ]; then
              python -m pip install -r requirements.txt
            fi

            echo "Virtualenv activated. python=$(which python)"
          '';
        };
      });
}
