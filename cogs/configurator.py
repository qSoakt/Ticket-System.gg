import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
import sqlite3
import logging

# Logging initialisieren
logging.basicConfig(level=logging.INFO)

class ticket_configurator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('config/ticket_settings.db')
        self.create_table()

        # Initialize settings
        self.ticket_category = None
        self.support_roles = []
        self.log_channel = None
        self.ticket_ui_channel = None

        # Default UI Embed for final preview
        self.final_preview_embed = discord.Embed(
            title="🎫 Ticket System Summary",
            description="Here are your ticket system settings:",
            color=discord.Color.blue()
        )

    def create_table(self):
        """Create the database table if it doesn't exist."""
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS ticket_settings (
                    guild_id INTEGER PRIMARY KEY,
                    category_id INTEGER,
                    support_roles TEXT,
                    log_channel_id INTEGER,
                    ticket_ui_channel_id INTEGER
                )
            ''')

    def save_settings(self, guild_id, category_id=None, support_roles=None, log_channel_id=None, ticket_ui_channel_id=None):
        """Save the settings to the database for the given guild."""
        with self.conn:
            self.conn.execute('''
                INSERT INTO ticket_settings (guild_id, category_id, support_roles, log_channel_id, ticket_ui_channel_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    category_id=excluded.category_id,
                    support_roles=excluded.support_roles,
                    log_channel_id=excluded.log_channel_id,
                    ticket_ui_channel_id=excluded.ticket_ui_channel_id
            ''', (guild_id, category_id, support_roles, log_channel_id, ticket_ui_channel_id))

    def load_settings(self, guild_id):
        """Load the settings from the database for the given guild."""
        cursor = self.conn.execute('SELECT category_id, support_roles, log_channel_id, ticket_ui_channel_id FROM ticket_settings WHERE guild_id = ?', (guild_id,))
        return cursor.fetchone()

    ticket = SlashCommandGroup("ticket", "Commands related to the ticket system")

    @ticket.command(name="setup", description="Configure the ticket system")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx):
        await ctx.respond("🎛️ **Ticket configuration** has been started. Please follow the instructions.", ephemeral=True)
        await self.start_category_selection(ctx)

    async def start_category_selection(self, ctx):
        """Step 1: Select the category for tickets."""
        categories = [cat for cat in ctx.guild.categories]

        options = [
            discord.SelectOption(label=f"📁 {cat.name}", value=str(cat.id)) for cat in categories
        ]

        select_view = CategorySelectView(self, options)
        await ctx.respond("📁 **Select the category for tickets**", view=select_view, ephemeral=True)

    async def start_support_role_selection(self, interaction):
        """Step 2: Select support roles."""
        roles = [role for role in interaction.guild.roles if role != interaction.guild.default_role]

        options = [
            discord.SelectOption(label=f"👤 {role.name}", value=str(role.id)) for role in roles
        ]

        select_view = RoleSelectView(self, options)
        await interaction.response.send_message("👤 **Select the support roles**", view=select_view, ephemeral=True)

    async def start_log_channel_selection(self, interaction):
        """Step 3: Select the log channel."""
        channels = [ch for ch in interaction.guild.text_channels]

        options = [
            discord.SelectOption(label=f"📄 {ch.name}", value=str(ch.id)) for ch in channels
        ]

        select_view = LogChannelSelectView(self, options)
        await interaction.response.send_message("📄 **Select the log channel for tickets**", view=select_view, ephemeral=True)

    async def start_ticket_ui_channel_selection(self, interaction):
        """Step 4: Select the channel for the ticket creation UI."""
        channels = [ch for ch in interaction.guild.text_channels]

        options = [
            discord.SelectOption(label=f"💬 {ch.name}", value=str(ch.id)) for ch in channels
        ]

        select_view = TicketUIChannelSelectView(self, options)
        await interaction.response.send_message("💬 **Select the channel for the ticket creation UI**", view=select_view, ephemeral=True)

    def update_final_preview(self, ctx):
        """Update the final preview embed with all selected settings."""
        self.final_preview_embed.clear_fields()

        # Add the final selected options to the preview embed
        self.final_preview_embed.add_field(name="📁 Ticket Category", value=f"<#{self.ticket_category}>" if self.ticket_category else "Not selected", inline=False)
        self.final_preview_embed.add_field(name="👤 Support Roles", value=', '.join([f"<@&{role_id}>" for role_id in self.support_roles]) if self.support_roles else "Not selected", inline=False)
        self.final_preview_embed.add_field(name="📄 Log Channel", value=f"<#{self.log_channel}>" if self.log_channel else "Not selected", inline=False)
        self.final_preview_embed.add_field(name="💬 Ticket UI Channel", value=f"<#{self.ticket_ui_channel}>" if self.ticket_ui_channel else "Not selected", inline=False)

        return self.final_preview_embed

    async def finish_setup(self, interaction):
        """Finish the setup and post the ticket creation UI."""
        # Final preview embed with all the settings
        final_embed = self.update_final_preview(interaction)

        # Ask for confirmation before finishing setup
        await interaction.response.send_message(embed=final_embed, view=FinishSetupView(self), ephemeral=True)

    async def post_ticket_ui(self, interaction: discord.Interaction):
        """Post the final ticket UI to the selected channel."""
        try:
            # Sende eine "Defer"-Antwort, um die Interaktion am Leben zu halten
            await interaction.response.defer(ephemeral=True)

            if not self.ticket_ui_channel:
                await interaction.followup.send("⚠️ Ticket UI channel is not selected! Please complete the setup.", ephemeral=True)
                return

            # Ticket UI Embed und Button
            ui_embed = discord.Embed(title="🎫 Create a Ticket", description="Click the button below to create a support ticket.", color=discord.Color.green())
            button_view = TicketCreateButtonView()

            # Hole den Channel und poste die UI
            channel = self.bot.get_channel(int(self.ticket_ui_channel))
            if channel:
                await channel.send(embed=ui_embed, view=button_view)

            # Sende die Abschlussnachricht als Follow-up
            await interaction.followup.send("✅ **Ticket system setup** has been completed successfully!", ephemeral=True)

        except discord.errors.NotFound as e:
            logging.error(f"Error in finishing setup: {e}")
            await interaction.followup.send("⚠️ Ein Fehler ist aufgetreten!", ephemeral=True)


# Select Views and Buttons

class CategorySelectView(discord.ui.View):
    """The view for selecting the ticket category."""
    def __init__(self, configurator, options):
        super().__init__(timeout=None)
        self.configurator = configurator
        self.add_item(CategorySelect(options, configurator))
        self.add_item(SaveAndContinueButton(configurator, step="support_role_selection"))

class CategorySelect(discord.ui.Select):
    """Dropdown to select a ticket category."""
    def __init__(self, options, configurator):
        super().__init__(placeholder="Select the category for tickets...", options=options)
        self.configurator = configurator

    async def callback(self, interaction: discord.Interaction):
        """Callback when a category is selected."""
        try:
            await interaction.response.defer()  # Antwort verzögern, falls es länger dauert
            self.configurator.ticket_category = self.values[0]
            self.configurator.save_settings(interaction.guild_id, category_id=self.values[0])
        except Exception as e:
            logging.error(f"Error in category selection: {e}")
            await interaction.response.send_message("⚠️ Ein Fehler ist aufgetreten!", ephemeral=True)

class RoleSelectView(discord.ui.View):
    """The view for selecting support roles."""
    def __init__(self, configurator, options):
        super().__init__(timeout=None)
        self.configurator = configurator
        self.add_item(RoleSelect(options, configurator))
        self.add_item(SaveAndContinueButton(configurator, step="log_channel_selection"))

class RoleSelect(discord.ui.Select):
    """Dropdown to select support roles."""
    def __init__(self, options, configurator):
        super().__init__(placeholder="Select support roles...", options=options)
        self.configurator = configurator

    async def callback(self, interaction: discord.Interaction):
        """Callback when support roles are selected."""
        try:
            await interaction.response.defer()
            self.configurator.support_roles = self.values
            self.configurator.save_settings(interaction.guild_id, support_roles=','.join(self.values))
        except Exception as e:
            logging.error(f"Error in role selection: {e}")
            await interaction.response.send_message("⚠️ Ein Fehler ist aufgetreten!", ephemeral=True)

class LogChannelSelectView(discord.ui.View):
    """The view for selecting the log channel."""
    def __init__(self, configurator, options):
        super().__init__(timeout=None)
        self.configurator = configurator
        self.add_item(LogChannelSelect(options, configurator))
        self.add_item(SaveAndContinueButton(configurator, step="ticket_ui_channel_selection"))

class LogChannelSelect(discord.ui.Select):
    """Dropdown to select the log channel."""
    def __init__(self, options, configurator):
        super().__init__(placeholder="Select the log channel...", options=options)
        self.configurator = configurator

    async def callback(self, interaction: discord.Interaction):
        """Callback when the log channel is selected."""
        try:
            await interaction.response.defer()
            self.configurator.log_channel = self.values[0]
            self.configurator.save_settings(interaction.guild_id, log_channel_id=self.values[0])
        except Exception as e:
            logging.error(f"Error in log channel selection: {e}")
            await interaction.response.send_message("⚠️ Ein Fehler ist aufgetreten!", ephemeral=True)

class TicketUIChannelSelectView(discord.ui.View):
    """The view for selecting the ticket UI channel."""
    def __init__(self, configurator, options):
        super().__init__(timeout=None)
        self.configurator = configurator
        self.add_item(TicketUIChannelSelect(options, configurator))
        self.add_item(SaveAndContinueButton(configurator, step="finish_setup"))

class TicketUIChannelSelect(discord.ui.Select):
    """Dropdown to select the ticket UI channel."""
    def __init__(self, options, configurator):
        super().__init__(placeholder="Select the ticket UI channel...", options=options)
        self.configurator = configurator

    async def callback(self, interaction: discord.Interaction):
        """Callback when the ticket UI channel is selected."""
        try:
            await interaction.response.defer()
            self.configurator.ticket_ui_channel = self.values[0]
            self.configurator.save_settings(interaction.guild_id, ticket_ui_channel_id=self.values[0])
        except Exception as e:
            logging.error(f"Error in ticket UI channel selection: {e}")
            await interaction.response.send_message("⚠️ Ein Fehler ist aufgetreten!", ephemeral=True)

# Finish and Continue Button

class SaveAndContinueButton(discord.ui.Button):
    """A button to save the selection and continue to the next step."""
    def __init__(self, configurator, step):
        super().__init__(label="Save and Continue", style=discord.ButtonStyle.green)
        self.configurator = configurator
        self.step = step

    async def callback(self, interaction: discord.Interaction):
        """Handle the button press."""
        try:
            if self.step == "support_role_selection":
                await self.configurator.start_support_role_selection(interaction)
            elif self.step == "log_channel_selection":
                await self.configurator.start_log_channel_selection(interaction)
            elif self.step == "ticket_ui_channel_selection":
                await self.configurator.start_ticket_ui_channel_selection(interaction)
            elif self.step == "finish_setup":
                await self.configurator.finish_setup(interaction)
        except Exception as e:
            logging.error(f"Error during setup continuation: {e}")
            await interaction.response.send_message("⚠️ Ein Fehler ist aufgetreten!", ephemeral=True)

class FinishSetupView(discord.ui.View):
    """View with the finish setup button."""
    def __init__(self, configurator):
        super().__init__(timeout=None)
        self.configurator = configurator  # Fix: Konfigurator-Referenz speichern
        self.add_item(FinishSetupButton(configurator))  # Die Referenz weitergeben


class FinishSetupButton(discord.ui.Button):
    """A button to finish the setup."""
    def __init__(self, configurator):
        super().__init__(label="Finish Setup", style=discord.ButtonStyle.green)
        self.configurator = configurator  # Fix: Die Referenz auf den Configurator speichern

    async def callback(self, interaction: discord.Interaction):
        """Handle the button press to finish setup."""
        try:
            await self.configurator.post_ticket_ui(interaction)
        except Exception as e:
            logging.error(f"Error in finishing setup: {e}")
            await interaction.response.send_message("⚠️ Ein Fehler ist aufgetreten!", ephemeral=True)


class TicketCreateButtonView(discord.ui.View):
    """View that shows the 'Create Ticket' button."""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCreateButton())

class TicketCreateButton(discord.ui.Button):
    """Button to create a ticket."""
    def __init__(self):
        super().__init__(label="Create Ticket", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🎟️ Your ticket has been created!", ephemeral=True)

def setup(bot):
    bot.add_cog(ticket_configurator(bot))
