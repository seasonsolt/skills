#!/usr/bin/env ruby
# frozen_string_literal: true

require "pathname"

root = Pathname(ARGV.fetch(0, "wiki/domain")).expand_path
abort "Domain wiki not found: #{root}" unless root.directory?

files = root.glob("**/*.md")
errors = []
warnings = []

files.each do |file|
  text = file.read
  text.scan(/(?<!!)\[[^\]]*\]\(([^)]+)\)/).flatten.each do |raw|
    target = raw.strip.sub(/^</, "").sub(/>$/, "").split(/\s+[\"']/).first
    next if target.nil? || target.empty? || target.start_with?("#")
    next if target.match?(/\A(?:https?:|mailto:|tel:)/)

    path = target.split("#", 2).first
    next if path.empty?

    resolved = (file.dirname + path).cleanpath
    errors << "BROKEN_LINK #{file}: #{target}" unless resolved.exist?
  end
end

definition_specs = {
  "CAP" => [/\| `(CAP-\d{3})` \|/, ->(path, _line) { path.to_s.end_with?("coverage/COVERAGE-LEDGER.md") }],
  "Q" => [/^- `(Q-\d{3})`[：:]/, ->(_path, _line) { true }],
  "RULE" => [/^- `(RULE-[A-Z]+-\d{3})`[：:]/, ->(_path, _line) { true }],
  "SCN" => [/^## `(SCN-[A-Z]+-\d{3})`/, ->(_path, _line) { true }],
  "EVT" => [/^- `(EVT-[A-Z]+-\d{3})\s/, ->(_path, _line) { true }]
}

reference_patterns = {
  "CAP" => /\bCAP-\d{3}\b/,
  "Q" => /\bQ-\d{3}\b/,
  "RULE" => /\bRULE-[A-Z]+-\d{3}\b/,
  "SCN" => /\bSCN-[A-Z]+-\d{3}\b/,
  "EVT" => /\bEVT-[A-Z]+-\d{3}\b/
}

counts = {}

definition_specs.each do |kind, (definition_pattern, owner)|
  definitions = Hash.new { |hash, key| hash[key] = [] }
  references = Hash.new { |hash, key| hash[key] = [] }

  files.each do |file|
    file.each_line.with_index(1) do |line, line_number|
      line.scan(reference_patterns.fetch(kind)) do |identifier|
        references[identifier] << "#{file}:#{line_number}"
      end

      match = line.match(definition_pattern)
      if match && owner.call(file, line)
        definitions[match[1]] << "#{file}:#{line_number}"
      end
    end
  end

  definitions.each do |identifier, locations|
    errors << "DUPLICATE_#{kind} #{identifier}: #{locations.join(', ')}" if locations.size > 1
  end

  (references.keys - definitions.keys).sort.each do |identifier|
    errors << "UNDEFINED_#{kind} #{identifier}: #{references[identifier].first}"
  end

  counts[kind] = definitions.size
end

required_metadata = %w[
  knowledge_status
  domain_owner
  maintainers
  last_reviewed
  coverage
  open_questions
]

(root.glob("subdomains/*/README.md") + root.glob("contexts/*/README.md")).each do |file|
  text = file.read
  required_metadata.each do |key|
    errors << "MISSING_METADATA #{file}: #{key}" unless text.match?(/^#{Regexp.escape(key)}:/)
  end
end

root.glob("subdomains/**/*.md").each do |file|
  file.each_line.with_index(1) do |line, line_number|
    if line.match?(/\b(?:SCN|EVT)-[A-Z]+-\d{3}\b/)
      errors << "STABLE_SCENARIO_OR_EVENT_IN_SUBDOMAIN #{file}:#{line_number}"
    end
  end
end

implementation_terms = /mapper|controller|feign|dubbo|redis|mybatis|\.xml|services\/|src\//i
root.glob("contexts/*/CONTEXT.md").each do |file|
  file.each_line.with_index(1) do |line, line_number|
    if line.match?(implementation_terms)
      errors << "CONTEXT_IMPLEMENTATION_TERM #{file}:#{line_number}"
    end
  end
end

coverage_ledger = root.join("coverage/COVERAGE-LEDGER.md")
if coverage_ledger.exist?
  unresolved_rows = coverage_ledger.each_line.select do |line|
    line.include?("`CAP-") && line.match?(/\|\s*(?:待发现|待分类)\s*\|/)
  end
  unless unresolved_rows.empty?
    warnings << "UNRESOLVED_CAPABILITY_ROWS #{coverage_ledger}: #{unresolved_rows.size}"
  end
end

puts "ROOT=#{root}"
puts "MARKDOWN=#{files.size}"
puts "SUBDOMAINS=#{root.glob('subdomains/*/README.md').size}"
puts "CONTEXTS=#{root.glob('contexts/*/README.md').size}"
puts "CONTEXT_GLOSSARIES=#{root.glob('contexts/*/CONTEXT.md').size}"
counts.each { |kind, count| puts "#{kind}_DEFINITIONS=#{count}" }
warnings.each { |warning| warn "WARNING #{warning}" }

if errors.empty?
  puts "ALL_MECHANICAL_GATES_OK"
else
  errors.each { |error| warn "ERROR #{error}" }
  exit 1
end
