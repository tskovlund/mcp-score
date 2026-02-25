{
  description = "mcp-score — MCP server for AI-driven music score generation and manipulation";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      forAllSystems = nixpkgs.lib.genAttrs [
        "aarch64-darwin"
        "x86_64-linux"
      ];
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              python313
              uv
              ruff
              pyright
            ];

            shellHook = ''
              git config core.hooksPath .githooks

              if [ ! -d .venv ]; then
                uv venv --python python3.13
              fi
              source .venv/bin/activate
              uv sync
            '';
          };
        }
      );
    };
}
