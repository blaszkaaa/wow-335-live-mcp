local addon = CreateFrame("Frame")
local export = {}
local WIRE_FIELDS = "captured_at,character,location,target,pet,quests,quest_log,bags,equipment,spells,actions,skills,stats,talents,group,buffs,debuffs,interaction,combat_summary,name,id,level,title,complete,ready_to_turn_in,failed,daily,watched,suggested_group,objectives,text,kind,done,count,slot,bag,rank,tab,health,health_max,power,power_max,money_copper,price_copper,status,npc,items,services,available_quests,active_quests,options,spell,damage_done,damage_taken,healing_done,healing_taken,deaths,casts,misses,duration,active,stock"
local WIRE_TOKENS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
local WIRE_KEYS = {}
local wire_index = 0
for field in string.gmatch(WIRE_FIELDS, "[^,]+") do
    wire_index = wire_index + 1
    WIRE_KEYS[field] = "~" .. string.sub(WIRE_TOKENS, wire_index, wire_index)
end

local function array()
    return { __array = true }
end

local function escape(value)
    return '"' .. string.gsub(value, '[%c\\"]', function(c)
        if c == '"' then return '\\"' end
        if c == '\\' then return '\\\\' end
        return string.format('\\u%04x', string.byte(c))
    end) .. '"'
end

local function encode(value, compact)
    local kind = type(value)
    if kind == "string" then return escape(value) end
    if kind == "number" then
        if value ~= value or value == math.huge or value == -math.huge then return "null" end
        return tostring(value)
    end
    if kind == "boolean" then return value and "true" or "false" end
    if kind ~= "table" then return "null" end

    local parts = {}
    if value.__array then
        for index = 1, #value do
            parts[#parts + 1] = encode(value[index], compact)
        end
        return "[" .. table.concat(parts, ",") .. "]"
    end
    for key, item in pairs(value) do
        if item ~= nil then
            parts[#parts + 1] = escape(compact and (WIRE_KEYS[key] or tostring(key)) or tostring(key)) .. ":" .. encode(item, compact)
        end
    end
    return "{" .. table.concat(parts, ",") .. "}"
end

local function item_id(link)
    if not link then return nil end
    return tonumber(string.match(link, "item:(%d+)"))
end

local function link_name(link)
    if not link then return nil end
    return string.match(link, "%[(.-)%]")
end

local function collect_quests()
    local quests = array()
    local count = GetNumQuestLogEntries() or 0
    for index = 1, count do
        local title, level, tag, suggestedGroup, isHeader, isCollapsed, complete, isDaily, questID = GetQuestLogTitle(index)
        if title and not isHeader then
            local required_money = GetQuestLogRequiredMoney and GetQuestLogRequiredMoney(index) or 0
            local quest = {
                id = questID,
                title = title,
                level = level,
                tag = tag,
                suggested_group = suggestedGroup,
                complete = complete,
                status = complete == 1 and "complete" or (complete == -1 and "failed" or "in_progress"),
                ready_to_turn_in = complete == 1 and (required_money or 0) <= GetMoney(),
                failed = complete == -1,
                watched = IsQuestWatched and IsQuestWatched(index) and true or false,
                required_money_copper = required_money,
                daily = isDaily and true or false,
                objectives = array(),
            }
            local objective_count = GetNumQuestLeaderBoards(index) or 0
            for objective_index = 1, objective_count do
                local text, kind, done = GetQuestLogLeaderBoard(objective_index, index)
                if text then
                    quest.objectives[#quest.objectives + 1] = {
                        text = text,
                        kind = kind,
                        done = done and true or false,
                    }
                end
            end
            quests[#quests + 1] = quest
        end
    end
    return quests
end

local function collect_bags()
    local bags = array()
    for bag = 0, 4 do
        local slots = GetContainerNumSlots(bag) or 0
        for slot = 1, slots do
            local texture, count, locked, quality, readable, lootable, link = GetContainerItemInfo(bag, slot)
            link = link or GetContainerItemLink(bag, slot)
            if link then
                bags[#bags + 1] = {
                    bag = bag,
                    slot = slot,
                    id = item_id(link),
                    name = link_name(link),
                    link = link,
                    count = count or 1,
                    quality = quality,
                }
            end
        end
    end
    return bags
end

local function collect_equipment()
    local equipment = array()
    for slot = 1, 19 do
        local link = GetInventoryItemLink("player", slot)
        if link then
            equipment[#equipment + 1] = {
                slot = slot,
                id = item_id(link),
                name = link_name(link),
                link = link,
            }
        end
    end
    return equipment
end

local function collect_spells()
    local spells = array()
    local tabs = GetNumSpellTabs() or 0
    for tab = 1, tabs do
        local tab_name, _, offset, count = GetSpellTabInfo(tab)
        if offset and count then
            for index = offset + 1, offset + count do
                local name, rank = GetSpellName(index, BOOKTYPE_SPELL)
                if name then
                    spells[#spells + 1] = {
                        name = name,
                        rank = rank,
                        tab = tab_name,
                    }
                end
            end
        end
    end
    return spells
end

local function collect_auras(unit, harmful)
    local result = array()
    if not UnitExists(unit) then return result end
    local getter = harmful and UnitDebuff or UnitBuff
    for index = 1, 40 do
        local name, rank, _, count, kind, duration, expires, caster, _, _, spellID = getter(unit, index)
        if not name then break end
        result[#result + 1] = {
            name = name,
            rank = rank,
            count = count,
            kind = kind,
            remaining = expires and expires > 0 and math.max(0, math.floor(expires - GetTime())) or nil,
            duration = duration,
            caster = caster,
            id = spellID,
        }
    end
    return result
end

local function collect_actions()
    local result = array()
    for slot = 1, 120 do
        if HasAction(slot) then
            local kind, id = GetActionInfo(slot)
            local name = nil
            if kind == "spell" and id then name = GetSpellInfo(id) end
            if kind == "item" and id then name = GetItemInfo(id) end
            if kind == "macro" and id then name = GetMacroInfo(id) end
            local start, duration, enabled = GetActionCooldown(slot)
            result[#result + 1] = {
                slot = slot,
                kind = kind,
                id = id,
                name = name,
                usable = IsUsableAction(slot) and true or false,
                cooldown = enabled == 1 and duration and duration > 0 and
                    math.max(0, math.floor(start + duration - GetTime())) or 0,
            }
        end
    end
    return result
end

local function collect_skills()
    local result = array()
    for index = 1, (GetNumSkillLines() or 0) do
        local name, isHeader, _, rank, _, _, maximum = GetSkillLineInfo(index)
        if name and not isHeader then
            result[#result + 1] = { name = name, rank = rank, maximum = maximum }
        end
    end
    return result
end

local function collect_stats()
    local stats = {}
    local names = { "strength", "agility", "stamina", "intellect", "spirit" }
    for index = 1, 5 do
        local _, value = UnitStat("player", index)
        stats[names[index]] = value
    end
    local _, armor = UnitArmor("player")
    stats.armor = armor
    local base, positive, negative = UnitAttackPower("player")
    stats.attack_power = (base or 0) + (positive or 0) + (negative or 0)
    if GetCritChance then stats.melee_crit_percent = GetCritChance() end
    if GetRangedCritChance then stats.ranged_crit_percent = GetRangedCritChance() end
    return stats
end

local function collect_talents()
    local result = array()
    for tab = 1, (GetNumTalentTabs() or 0) do
        local tree = GetTalentTabInfo(tab)
        for index = 1, (GetNumTalents(tab) or 0) do
            local name, _, tier, column, rank = GetTalentInfo(tab, index)
            if name and rank and rank > 0 then
                result[#result + 1] = {
                    name = name, tree = tree, tier = tier,
                    column = column, rank = rank,
                }
            end
        end
    end
    return result
end

local function collect_group()
    local result = array()
    local raid_count = GetNumRaidMembers() or 0
    local party_count = GetNumPartyMembers() or 0
    if raid_count > 0 then
        for index = 1, raid_count do
            local unit = "raid" .. index
            if UnitExists(unit) then
                result[#result + 1] = {
                    name = UnitName(unit), level = UnitLevel(unit),
                    health = UnitHealth(unit), health_max = UnitHealthMax(unit),
                }
            end
        end
    elseif party_count > 0 then
        for index = 1, party_count do
            local unit = "party" .. index
            if UnitExists(unit) then
                result[#result + 1] = {
                    name = UnitName(unit), level = UnitLevel(unit),
                    health = UnitHealth(unit), health_max = UnitHealthMax(unit),
                }
            end
        end
    end
    return result
end

local interaction_kind = nil
local interaction_snapshot = nil
local function pack_args(...)
    return { n = select("#", ...), ... }
end

local function collect_interaction()
    if not interaction_kind then return nil end
    local result = {
        kind = interaction_kind,
        npc = UnitName("npc") or UnitName("target"),
        captured_at = time(),
        open = true,
    }
    if interaction_kind == "trainer" and GetNumTrainerServices then
        local total = GetNumTrainerServices() or 0
        result.total = total
        result.truncated = total > 100
        result.services = array()
        for index = 1, math.min(total, 100) do
            local name, rank, category = GetTrainerServiceInfo(index)
            if name and category ~= "header" then
                local skill_name, skill_level = GetTrainerServiceSkillReq(index)
                result.services[#result.services + 1] = {
                    name = name, rank = rank, status = category,
                    price_copper = GetTrainerServiceCost(index),
                    level_required = GetTrainerServiceLevelReq(index),
                    skill_required = skill_name,
                    skill_level_required = skill_level,
                }
            end
        end
    elseif interaction_kind == "merchant" and GetMerchantNumItems then
        local total = GetMerchantNumItems() or 0
        result.total = total
        result.truncated = total > 100
        result.items = array()
        for index = 1, math.min(total, 100) do
            local name, _, price, stack, stock, usable, extended = GetMerchantItemInfo(index)
            local link = GetMerchantItemLink(index)
            if name then
                result.items[#result.items + 1] = {
                    name = name, id = item_id(link), price_copper = price,
                    count = stack, stock = stock, usable = usable and true or false,
                    extended_cost = extended and true or false,
                }
            end
        end
    elseif interaction_kind == "gossip" and GetGossipOptions then
        result.text = string.sub(GetGossipText() or "", 1, 350)
        result.available_quests = array()
        local available = pack_args(GetGossipAvailableQuests())
        for index = 1, available.n, 5 do
            result.available_quests[#result.available_quests + 1] = {
                title = available[index], level = available[index + 1],
                trivial = available[index + 2] and true or false,
                daily = available[index + 3] and true or false,
            }
        end
        result.active_quests = array()
        local active = pack_args(GetGossipActiveQuests())
        for index = 1, active.n, 4 do
            result.active_quests[#result.active_quests + 1] = {
                title = active[index], level = active[index + 1],
                complete = active[index + 3] and true or false,
            }
        end
        result.options = array()
        local options = pack_args(GetGossipOptions())
        for index = 1, options.n, 2 do
            result.options[#result.options + 1] = {
                text = options[index], kind = options[index + 1],
            }
        end
    elseif interaction_kind == "quest" then
        result.title = GetTitleText and GetTitleText() or nil
        result.text = GetQuestText and string.sub(GetQuestText() or "", 1, 600) or nil
        result.objective_text = GetObjectiveText and string.sub(GetObjectiveText() or "", 1, 400) or nil
        result.reward_text = GetRewardText and string.sub(GetRewardText() or "", 1, 400) or nil
        result.ready_to_turn_in = IsQuestCompletable and IsQuestCompletable() and true or false
    end
    return result
end

local combat_summary = nil
local player_guid = nil
local function new_combat_summary()
    combat_summary = {
        active = true, started_at = time(), damage_done = 0, damage_taken = 0,
        healing_done = 0, healing_taken = 0, deaths = 0, misses = 0,
        casts = array(),
    }
end

local function record_combat_event(...)
    local _, subevent, source_guid, _, _, dest_guid, dest_name = ...
    if not subevent or not player_guid then return end
    local pet_guid = UnitExists("pet") and UnitGUID("pet") or nil
    local player_source = source_guid == player_guid
    local friendly_source = player_source or (pet_guid and source_guid == pet_guid)
    local player_dest = dest_guid == player_guid
    if not friendly_source and not player_dest then return end
    if not combat_summary or not combat_summary.active then
        if not UnitAffectingCombat("player") then return end
        new_combat_summary()
    end
    if friendly_source and dest_name and dest_guid ~= player_guid then
        combat_summary.last_enemy = dest_name
    end
    local amount = nil
    if subevent == "SWING_DAMAGE" then
        amount = select(9, ...)
    elseif subevent == "SPELL_DAMAGE" or subevent == "SPELL_PERIODIC_DAMAGE" or
           subevent == "RANGE_DAMAGE" or subevent == "DAMAGE_SHIELD" then
        amount = select(12, ...)
    end
    if type(amount) == "number" then
        if friendly_source then combat_summary.damage_done = combat_summary.damage_done + amount end
        if player_dest then combat_summary.damage_taken = combat_summary.damage_taken + amount end
    end
    if subevent == "SPELL_HEAL" or subevent == "SPELL_PERIODIC_HEAL" then
        local heal = select(12, ...)
        if type(heal) == "number" then
            if friendly_source then combat_summary.healing_done = combat_summary.healing_done + heal end
            if player_dest then combat_summary.healing_taken = combat_summary.healing_taken + heal end
        end
    end
    if player_source and subevent == "SPELL_CAST_SUCCESS" then
        local spell_name = select(10, ...)
        if spell_name then
            local casts = combat_summary.casts
            casts[#casts + 1] = spell_name
            if #casts > 8 then table.remove(casts, 1) end
        end
    end
    if friendly_source and string.find(subevent, "_MISSED", 1, true) then
        combat_summary.misses = combat_summary.misses + 1
    end
    if player_dest and subevent == "UNIT_DIED" then
        combat_summary.deaths = combat_summary.deaths + 1
    end
end

local function collect()
    if not UnitExists("player") then return end
    if not player_guid then player_guid = UnitGUID("player") end
    local name = UnitName("player")
    local _, class = UnitClass("player")
    local _, race = UnitRace("player")
    local x, y = GetPlayerMapPosition("player")
    local target = nil
    if UnitExists("target") then
        target = {
            name = UnitName("target"),
            guid = UnitGUID("target"),
            level = UnitLevel("target"),
            health = UnitHealth("target"),
            health_max = UnitHealthMax("target"),
            power = UnitPower("target"),
            power_max = UnitPowerMax("target"),
            classification = UnitClassification("target"),
            dead = UnitIsDead("target") and true or false,
            hostile = UnitCanAttack("player", "target") and true or false,
            buffs = collect_auras("target", false),
            debuffs = collect_auras("target", true),
        }
    end
    local pet = nil
    if UnitExists("pet") then
        pet = {
            name = UnitName("pet"),
            level = UnitLevel("pet"),
            health = UnitHealth("pet"),
            health_max = UnitHealthMax("pet"),
            power = UnitPower("pet"),
            power_max = UnitPowerMax("pet"),
        }
    end
    local quest_entries, quest_count = GetNumQuestLogEntries()
    if interaction_kind then interaction_snapshot = collect_interaction() end
    if combat_summary then
        combat_summary.duration = math.max(0, (combat_summary.ended_at or time()) - combat_summary.started_at)
    end
    export = {
        captured_at = time(),
        character = {
            name = name,
            realm = GetRealmName(),
            class = class,
            race = race,
            level = UnitLevel("player"),
            xp = UnitXP("player"),
            xp_max = UnitXPMax("player"),
            health = UnitHealth("player"),
            health_max = UnitHealthMax("player"),
            power_type = UnitPowerType("player"),
            power = UnitPower("player"),
            power_max = UnitPowerMax("player"),
            money_copper = GetMoney(),
            combat = UnitAffectingCombat("player") and true or false,
            dead = UnitIsDeadOrGhost("player") and true or false,
        },
        location = {
            zone = GetZoneText(),
            subzone = GetSubZoneText(),
            map_x = x and x > 0 and x or nil,
            map_y = y and y > 0 and y or nil,
        },
        target = target,
        pet = pet,
        quests = collect_quests(),
        quest_log = { entries = quest_entries, quests = quest_count },
        bags = collect_bags(),
        equipment = collect_equipment(),
        spells = collect_spells(),
        actions = collect_actions(),
        skills = collect_skills(),
        stats = collect_stats(),
        talents = collect_talents(),
        group = collect_group(),
        buffs = collect_auras("player", false),
        debuffs = collect_auras("player", true),
        interaction = interaction_snapshot and
            (interaction_snapshot.open or not interaction_snapshot.closed_at or
             time() - interaction_snapshot.closed_at <= 30) and interaction_snapshot or nil,
        combat_summary = combat_summary,
    }
end

addon:RegisterEvent("PLAYER_ENTERING_WORLD")
addon:RegisterEvent("PLAYER_LOGOUT")
addon:RegisterEvent("PLAYER_REGEN_DISABLED")
addon:RegisterEvent("PLAYER_REGEN_ENABLED")
addon:RegisterEvent("COMBAT_LOG_EVENT_UNFILTERED")
addon:RegisterEvent("TRAINER_SHOW")
addon:RegisterEvent("TRAINER_UPDATE")
addon:RegisterEvent("TRAINER_CLOSED")
addon:RegisterEvent("MERCHANT_SHOW")
addon:RegisterEvent("MERCHANT_UPDATE")
addon:RegisterEvent("MERCHANT_CLOSED")
addon:RegisterEvent("GOSSIP_SHOW")
addon:RegisterEvent("GOSSIP_CLOSED")
addon:RegisterEvent("QUEST_DETAIL")
addon:RegisterEvent("QUEST_PROGRESS")
addon:RegisterEvent("QUEST_COMPLETE")
addon:RegisterEvent("QUEST_FINISHED")
addon:SetScript("OnEvent", function(_, event, ...)
    if event == "PLAYER_ENTERING_WORLD" then
        player_guid = UnitGUID("player")
        collect()
    elseif event == "PLAYER_LOGOUT" then
        collect()
        WoWMCPExport = encode(export)
    elseif event == "PLAYER_REGEN_DISABLED" then
        new_combat_summary()
    elseif event == "PLAYER_REGEN_ENABLED" then
        if combat_summary then
            combat_summary.active = false
            combat_summary.ended_at = time()
        end
    elseif event == "COMBAT_LOG_EVENT_UNFILTERED" then
        record_combat_event(...)
    elseif event == "TRAINER_SHOW" or event == "TRAINER_UPDATE" then
        interaction_kind = "trainer"
        interaction_snapshot = collect_interaction()
    elseif event == "MERCHANT_SHOW" or event == "MERCHANT_UPDATE" then
        interaction_kind = "merchant"
        interaction_snapshot = collect_interaction()
    elseif event == "GOSSIP_SHOW" then
        interaction_kind = "gossip"
        interaction_snapshot = collect_interaction()
    elseif event == "QUEST_DETAIL" or event == "QUEST_PROGRESS" or event == "QUEST_COMPLETE" then
        interaction_kind = "quest"
        interaction_snapshot = collect_interaction()
    elseif event == "TRAINER_CLOSED" or event == "MERCHANT_CLOSED" or
           event == "GOSSIP_CLOSED" or event == "QUEST_FINISHED" then
        interaction_kind = nil
        if interaction_snapshot then
            interaction_snapshot.open = false
            interaction_snapshot.closed_at = time()
        end
    end
end)

SLASH_WOWMCPDATA1 = "/wowmcp"
SlashCmdList.WOWMCPDATA = function()
    collect()
    DEFAULT_CHAT_FRAME:AddMessage("WoW MCP: dane zebrane. Wpisz /reload, aby zapisać je do pliku dla ChatGPT.")
end

-- The client cannot send files or network traffic from addon Lua. A small,
-- non-interactive color strip makes current API values available to a local
-- screenshot decoder without touching the WoW process memory.
local COLS, ROWS, CELL = 32, 16, 3
local PAGE_BYTES = COLS * ROWS - 14
local panel = CreateFrame("Frame", "WoWMCPDataPanel", UIParent)
panel:SetSize(COLS * CELL, ROWS * CELL)
panel:SetPoint("BOTTOMLEFT", UIParent, "BOTTOMLEFT", 8, 8)
panel:SetFrameStrata("TOOLTIP")
panel:SetFrameLevel(1000)
panel:EnableMouse(false)

local pixels = {}
for row = 0, ROWS - 1 do
    for col = 0, COLS - 1 do
        local pixel = panel:CreateTexture(nil, "OVERLAY")
        pixel:SetSize(CELL, CELL)
        pixel:SetPoint("TOPLEFT", panel, "TOPLEFT", col * CELL, -row * CELL)
        pixels[#pixels + 1] = pixel
    end
end

local payload = ""
local generation = 0
local page = 1
local pages = 1
local checksum = 0
local elapsed_time = 0
local refresh_age = 0
local native_refresh_age = 0

local function compact_items(items)
    local result = array()
    for _, item in ipairs(items) do
        result[#result + 1] = {
            item.id or 0, item.name or "", item.count or 0,
            item.bag or -1, item.slot or 0,
        }
    end
    return result
end

local function compact_spells(items)
    local result = array()
    for _, item in ipairs(items) do
        result[#result + 1] = { item.name or "", item.rank or "", item.tab or "" }
    end
    return result
end

local function compact_actions(items)
    local result = array()
    for _, item in ipairs(items) do
        result[#result + 1] = {
            item.slot or 0, item.kind or "", item.id or 0,
            item.name or "", item.usable and true or false, item.cooldown or 0,
        }
    end
    return result
end

local function compact_skills(items)
    local result = array()
    for _, item in ipairs(items) do
        result[#result + 1] = { item.name or "", item.rank or 0, item.maximum or 0 }
    end
    return result
end

local function compact_quests(quests)
    local result = array()
    for _, quest in ipairs(quests) do
        result[#result + 1] = {
            id = quest.id,
            title = quest.title,
            level = quest.level,
            complete = quest.complete,
            status = quest.status,
            ready_to_turn_in = quest.ready_to_turn_in,
            failed = quest.failed,
            watched = quest.watched,
            required_money_copper = quest.required_money_copper,
            daily = quest.daily,
            suggested_group = quest.suggested_group,
            objectives = quest.objectives,
        }
    end
    return result
end

-- Native bridge is optional. It exists only when a compatible, user-approved
-- WrathClassicAPI extension has registered WoWMCP.Publish in Lua.
-- The original visual strip remains a full fallback.
local native_session = tostring(time()) .. "-" .. tostring(math.random(1000, 999999))
local native_sequence = 0
local native_last_ok = false
local native_last_bytes = 0

local function native_available()
    return type(WoWMCP) == "table" and type(WoWMCP.Publish) == "function"
end

local function publish_native()
    if not native_available() then return end

    -- Keep the native payload human-readable, unlike the compact strip wire.
    local data = encode(export, false)
    if #data > 58000 then
        local slim = {
            captured_at = export.captured_at,
            character = export.character,
            location = export.location,
            target = export.target,
            pet = export.pet,
            quests = export.quests,
            quest_log = export.quest_log,
            bags = export.bags,
            equipment = export.equipment,
            stats = export.stats,
            talents = export.talents,
            group = export.group,
            interaction = export.interaction,
            combat_summary = export.combat_summary,
            spells_truncated = true,
            actions_truncated = true,
            skills_truncated = true,
        }
        data = encode(slim, false)
        if #data > 58000 then
            slim.bags = nil
            slim.bags_truncated = true
            data = encode(slim, false)
        end
        if #data > 58000 then
            slim.quests = nil
            slim.quests_truncated = true
            data = encode(slim, false)
        end
    end
    if #data > 58000 then
        native_last_ok = false
        return
    end
    local wrapped = '{"version":1,"session":"' .. native_session ..
        '","sequence":' .. tostring(native_sequence + 1) ..
        ',"kind":"snapshot","captured_at":' .. tostring(export.captured_at or time()) ..
        ',"data":' .. data .. '}'
    if #wrapped > 60000 then return end
    native_sequence = native_sequence + 1
    local success, sent = pcall(WoWMCP.Publish, wrapped)
    native_last_ok = success and sent and true or false
    if native_last_ok then native_last_bytes = #wrapped end
end

SLASH_WOWMCPNATIVE1 = "/wowmcpnative"
SlashCmdList.WOWMCPNATIVE = function()
    if not native_available() then
        DEFAULT_CHAT_FRAME:AddMessage("WoW MCP Native: brak funkcji DLL. Dziala tryb wizualny.")
    else
        DEFAULT_CHAT_FRAME:AddMessage("WoW MCP Native: " ..
            (native_last_ok and "ostatni pakiet wyslany" or "odbiornik niedostepny") ..
            ", bajtow: " .. tostring(native_last_bytes) ..
            ", sekwencja: " .. tostring(native_sequence))
    end
end

local function refresh_payload()
    collect()
    generation = (generation + 1) % 256
    local live = {
        wire_version = 3,
        captured_at = export.captured_at,
        character = export.character,
        location = export.location,
        target = export.target,
        pet = export.pet,
        quests = compact_quests(export.quests or {}),
        quest_log = export.quest_log,
        bags = compact_items(export.bags or {}),
        equipment = compact_items(export.equipment or {}),
        spells = compact_spells(export.spells or {}),
        actions = compact_actions(export.actions or {}),
        skills = compact_skills(export.skills or {}),
        stats = export.stats,
        talents = export.talents,
        group = export.group,
        buffs = export.buffs,
        debuffs = export.debuffs,
        interaction = export.interaction,
        combat_summary = export.combat_summary,
    }
    payload = encode(live, true)
    if #payload > 24000 then
        live.spells = nil
        live.spells_truncated = true
        payload = encode(live, true)
    end
    if #payload > 24000 then
        live.actions = nil
        live.actions_truncated = true
        payload = encode(live, true)
    end
    if #payload > 24000 then
        live.bags = nil
        live.bags_truncated = true
        payload = encode(live, true)
    end
    if #payload > 24000 then payload = encode({ error = "Dane przekraczaja limit paska MCP." }, true) end
    pages = math.max(1, math.ceil(#payload / PAGE_BYTES))
    checksum = 0
    for index = 1, #payload do
        checksum = (checksum + string.byte(payload, index)) % 65536
    end
end

local function render_page()
    local offset = (page - 1) * PAGE_BYTES
    local fragment = string.sub(payload, offset + 1, offset + PAGE_BYTES)
    local bytes = {
        87, 77, 67, 80, -- WMCP
        1, generation, page, pages,
        #fragment % 256, math.floor(#fragment / 256),
        #payload % 256, math.floor(#payload / 256),
        checksum % 256, math.floor(checksum / 256),
    }
    for index = 1, #fragment do
        bytes[#bytes + 1] = string.byte(fragment, index)
    end
    for index = 1, #pixels do
        local byte = bytes[index] or 0
        pixels[index]:SetTexture(math.floor(byte / 16) / 15, (byte % 16) / 15, 1)
    end
end

panel:SetScript("OnUpdate", function(_, elapsed)
    elapsed_time = elapsed_time + elapsed
    refresh_age = refresh_age + elapsed
    native_refresh_age = native_refresh_age + elapsed
    -- Native snapshots do not wait for all pages of the legacy visual strip.
    if native_refresh_age >= 3 and native_available() then
        native_refresh_age = 0
        collect()
        publish_native()
    end
    if elapsed_time < 0.18 then return end
    elapsed_time = 0
    page = page + 1
    if page > pages then
        if refresh_age >= 3 then
            refresh_payload()
            refresh_age = 0
        end
        page = 1
    end
    render_page()
end)

addon:HookScript("OnEvent", function(_, event)
    if event == "PLAYER_ENTERING_WORLD" then
        refresh_payload()
        page = 1
        render_page()
    end
end)
